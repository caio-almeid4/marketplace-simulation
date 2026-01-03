from typing import Any, Dict, List

from langchain.tools import BaseTool
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from agents.state import AgentState
from schemas.agent import AgentAnalysis, AgentConfig
from schemas.inventory import Inventory
from schemas.message import Message
from utils.render_template import render_template


class Agent:
    def __init__(self, config: AgentConfig, tools: Dict[str, BaseTool] = {}):
        self.config = config
        self.name = self.config.name
        self.inventory: Inventory = self.config.inventory
        self.energy = self.config.energy
        self.inbox: List[Message] = []
        self.internal_monologue = ''
        self.llm = self._get_llm(model='gpt-5-mini')
        self.graph = self._build_graph()
        self.tools = tools
        self.is_alive = True

    def _get_llm(self, model: str):

        return ChatOpenAI(
            model=model,
            temperature=self.config.temperature,
        )

    def _get_internal_memory(self) -> str:
        return render_template(
            'memory',
            {'internal_monologue': self.internal_monologue},
        )

    def _get_general_status(self) -> str:
        general_status = self.inventory.model_dump()
        general_status['energy'] = self.energy
        return render_template('general_status', general_status)

    def _get_inbox(self) -> str:
        return render_template('inbox', {'inbox': self.inbox})

    def _get_system_prompt(self) -> SystemMessage:
        system_prompt_info = self.config.personality_info.model_dump()
        system_prompt_info['name'] = self.name
        system_prompt = render_template('system_prompt', system_prompt_info)
        return SystemMessage(system_prompt)

    def _get_survival_protocol(self) -> SystemMessage:
        survival_prompt = render_template('survival_protocol', {'energy': self.energy})
        return SystemMessage(survival_prompt)
    
    def _get_bankrupt_protocol(self, rounds_left: int) -> SystemMessage:
        info = {'cash': self.inventory.cash, 'rounds_left': rounds_left}
        bankrupt_prompt = render_template('bankrupt_protocol', info)
        return SystemMessage(bankrupt_prompt)

    def _build_context(self, market_data: str, round: int) -> HumanMessage:

        context = f'-------- Round {round} --------'
        context += '\n'
        context += self._get_internal_memory()
        context += '\n\n'
        context += self._get_general_status()
        context += '\n\n'
        context += market_data
        context += '\n\n'
        context += self._get_inbox()

        return HumanMessage(context)

    def run_turn(self, market_data: str, round_num: int) -> Dict[str, Any]:

        messages = [
            self._get_system_prompt(),
            self._build_context(market_data, round=round_num),
        ]
        if self.config.operational_cost:
            rounds_left_by_cash = int(
                self.inventory.cash / self.config.operational_cost
            )
            if rounds_left_by_cash < 3:
                messages.append(self._get_bankrupt_protocol(rounds_left_by_cash))
            
        if self.energy < 3:
            messages.append(self._get_survival_protocol())
            
        initial_state = AgentState(
            internal_monologue=self.internal_monologue, messages=messages, next_step=''
        )

        result = self.graph.invoke(
            initial_state,
            config={
                'run_name': f'{self.name} turn',
                'tags': [self.name, f'Round_{round_num}'],
                'metadata': {
                    'inventory': self.inventory.model_dump(),
                    'current_round': round_num,
                    'monologue': self.internal_monologue,
                },
            },
        )
        self.internal_monologue = result['internal_monologue']
        self.inbox.clear()
        return result

    def _build_graph(self):

        graph = StateGraph(AgentState)
        graph.add_node('router', self._routing_node)
        graph.add_node('analyze_market', self._analyze_market)
        graph.add_node('manage_offers', self._manage_offers)

        graph.add_edge(START, 'analyze_market')
        graph.add_edge('analyze_market', 'router')
        graph.add_edge('manage_offers', END)

        return graph.compile()

    def _analyze_market(self, state: AgentState) -> Command:

        agent = self.llm.with_structured_output(AgentAnalysis)
        response = agent.invoke(state['messages'])

        return Command(
            update={
                'internal_monologue': response.get(
                    'updated_monologue', state['internal_monologue']
                    ),
                'next_step': response.get('next_step', 'wait'),
            }   
        )

    def _routing_node(self, state: AgentState) -> Command:
        next_step = state.get('next_step')

        if next_step in ('wait', '', None):
            return Command(goto=END)

        return Command(goto=next_step)

    def _manage_offers(self, state: AgentState) -> Command:

        agent = self.llm.bind_tools([
            self.tools['create_public_offer'],
            self.tools['accept_offer'],
        ])
        phase_prompt = SystemMessage(render_template('manage_offers_phase'))
        messages_to_llm = state['messages'] + [phase_prompt]
        response = agent.invoke(messages_to_llm)
        messages = [response]
        messages.extend(self._execute_tools(tool_calls=response.tool_calls))

        return Command(update={'messages': messages})

    def _execute_tools(self, tool_calls):

        tool_messages = []
        for call in tool_calls:
            result = self.tools[call['name']].invoke(call['args'])
            tool_messages.append(
                ToolMessage(
                    content=str(result),
                    tool_call_id=call['id'],
                )
            )
        return tool_messages
    
    def collect_operational_payment(self) -> bool:
        
        if self.inventory.cash < self.config.operational_cost:
            self.inventory.cash = 0
            return False
        
        self.inventory.cash -= self.config.operational_cost
        return True
