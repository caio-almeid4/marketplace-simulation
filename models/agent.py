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
        self.inbox: List[Message] = []
        self.internal_monologue = ''
        self.llm = self._get_llm()
        self.graph = self._build_graph()
        self.tools = tools

    def _get_llm(self):

        return ChatOpenAI(
            model='gpt-4o-mini',
            temperature=self.config.temperature,
        )

    def _get_internal_memory(self) -> str:
        return render_template(
            'memory',
            {'internal_monologue': self.internal_monologue},
        )

    def _get_inventory(self) -> str:
        return render_template('inventory', self.inventory.model_dump())

    def _get_inbox(self) -> str:
        return render_template('inbox', {'inbox': self.inbox})

    def _get_system_prompt(self) -> SystemMessage:
        system_prompt_info = self.config.personality_info.model_dump()
        system_prompt_info['name'] = self.name
        system_prompt = render_template('system_prompt', system_prompt_info)
        return SystemMessage(system_prompt)

    def _build_context(self, market_data: str, round: int) -> HumanMessage:

        context = f'-------- Round {round} --------'
        context += '\n'
        context += self._get_internal_memory()
        context += '\n\n'
        context += self._get_inventory()
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
                'internal_monologue': response['updated_monologue'],
                'next_step': response['next_step'],
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
