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
from settings import general_settings
from utils.render_template import render_template


class Agent:
    """Autonomous economic agent that trades in the marketplace simulation.

    Each agent has a personality, inventory, energy, and uses a LangGraph workflow
    to make trading decisions. Agents receive market data each round, analyze it,
    and execute trades using provided tools.

    Attributes:
        config: Configuration defining personality, inventory, and behavior.
        name: Unique identifier for the agent.
        inventory: Current holdings (cash, apple, chip, gold).
        energy: Survival resource that depletes each round.
        inbox: Messages from broadcasts or other events.
        internal_monologue: Private memory for strategic planning.
        llm: Language model for decision making.
        graph: LangGraph workflow (analyze → route → manage_offers).
        tools: Trading tools available to the agent.
        is_alive: Whether the agent is still participating.
    """

    def __init__(self, config: AgentConfig, tools: Dict[str, BaseTool] = {}):
        """Initialize the Agent.

        Args:
            config: Agent configuration with personality and starting inventory.
            tools: Dictionary of trading tools (injected by simulation).
        """
        self.config = config
        self.name = self.config.name
        self.inventory: Inventory = self.config.inventory
        self.energy = self.config.energy
        self.inbox: List[Message] = []
        self.internal_monologue = ''
        self.llm = self._get_llm()
        self.graph = self._build_graph()
        self.tools = tools
        self.is_alive = True

    def _get_llm(self):
        """Create and configure the language model for this agent.

        Returns:
            Configured ChatOpenAI instance with agent's model and temperature.
        """
        return ChatOpenAI(
            model=self.config.model,
            temperature=self.config.temperature,
        )

    def _get_internal_memory(self) -> str:
        """Render the agent's internal monologue as formatted text.

        Returns:
            Rendered template string containing the internal monologue.
        """
        return render_template(
            'memory',
            {'internal_monologue': self.internal_monologue},
        )

    def _get_general_status(self) -> str:
        """Render current inventory and energy status.

        Returns:
            Rendered template string with cash, items, and energy.
        """
        general_status = self.inventory.model_dump()
        general_status['energy'] = self.energy
        return render_template('general_status', general_status)

    def _get_inbox(self) -> str:
        """Render messages from inbox (broadcasts, events).

        Returns:
            Rendered template string containing inbox messages.
        """
        return render_template('inbox', {'inbox': self.inbox})

    def _get_system_prompt(self) -> SystemMessage:
        """Generate the system prompt with personality and rules.

        Returns:
            SystemMessage containing agent personality, objectives, and game rules.
        """
        system_prompt_info = self.config.personality_info.model_dump()
        system_prompt_info['name'] = self.name
        system_prompt_info['operational_cost'] = self.config.operational_cost
        system_prompt = render_template('system_prompt', system_prompt_info)
        return SystemMessage(system_prompt)

    def _get_survival_protocol(self) -> SystemMessage:
        """Generate warning message when energy is low.

        Returns:
            SystemMessage alerting agent about low energy levels.
        """
        survival_prompt = render_template('survival_protocol', {'energy': self.energy})
        return SystemMessage(survival_prompt)

    def _get_bankrupt_protocol(self, rounds_left: int) -> SystemMessage:
        """Generate warning message when cash is running low.

        Args:
            rounds_left: Number of rounds agent can survive with current cash.

        Returns:
            SystemMessage alerting agent about bankruptcy risk.
        """
        info = {'cash': self.inventory.cash, 'rounds_left': rounds_left}
        bankrupt_prompt = render_template('bankrupt_protocol', info)
        return SystemMessage(bankrupt_prompt)

    def _build_context(self, market_data: str, round: int) -> HumanMessage:
        """Build the complete context message for the agent's turn.

        Combines internal memory, status, market data, and inbox into a single
        formatted message for the agent to process.

        Args:
            market_data: Current market offers and recent trades.
            round: Current round number.

        Returns:
            HumanMessage containing all context for decision making.
        """
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
        """Execute one turn of the agent's decision-making workflow.

        Builds context, adds survival/bankruptcy warnings if needed, and runs
        the LangGraph workflow (analyze → route → manage_offers). Updates
        internal state after execution.

        Args:
            market_data: Current market state with offers and trades.
            round_num: Current round number in the simulation.

        Returns:
            Dictionary containing workflow results and updated state.
        """
        messages = [
            self._get_system_prompt(),
            self._build_context(market_data, round=round_num),
        ]
        if self.config.operational_cost:
            rounds_left_by_cash = int(
                self.inventory.cash / self.config.operational_cost
            )
            if rounds_left_by_cash < general_settings.rounds_left_to_alert:
                messages.append(self._get_bankrupt_protocol(rounds_left_by_cash))

        if self.energy < general_settings.energy_qty_to_alert:
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
        """Build the LangGraph workflow for agent decision-making.

        Creates a state graph with three nodes:
        - analyze_market: Analyzes context and plans strategy
        - router: Decides whether to trade or wait
        - manage_offers: Executes trades using tools

        Returns:
            Compiled LangGraph workflow.
        """
        graph = StateGraph(AgentState)
        graph.add_node('router', self._routing_node)
        graph.add_node('analyze_market', self._analyze_market)
        graph.add_node('manage_offers', self._manage_offers)

        graph.add_edge(START, 'analyze_market')
        graph.add_edge('analyze_market', 'router')
        graph.add_edge('manage_offers', END)

        return graph.compile()

    def _analyze_market(self, state: AgentState) -> Command:
        """Phase 1: Analyze market context and formulate strategy.

        Uses structured output to extract updated internal monologue and
        next action decision from the LLM.

        Args:
            state: Current agent state with messages and context.

        Returns:
            Command with updated monologue and next_step routing decision.
        """
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

    @staticmethod
    def _routing_node(state: AgentState) -> Command:
        """Phase 2: Route to action node or end based on agent's decision.

        Args:
            state: Current agent state with next_step decision.

        Returns:
            Command routing to manage_offers or END.
        """
        next_step = state.get('next_step')

        if next_step in general_settings.next_step_wait:
            return Command(goto=END)

        return Command(goto='manage_offers')

    def _manage_offers(self, state: AgentState) -> Command:
        """Phase 3: Execute trades using available tools.

        Binds all trading tools to the LLM and allows it to execute the
        strategy formulated in the analysis phase.

        Args:
            state: Current agent state with messages.

        Returns:
            Command with updated messages including tool results.
        """
        agent = self.llm.bind_tools([
            self.tools['create_public_offer'],
            self.tools['accept_sell_offer'],
            self.tools['create_buy_offer'],
            self.tools['accept_buy_offer'],
            self.tools['cancel_offer'],
        ])
        phase_prompt = SystemMessage(render_template('manage_offers_phase'))
        messages_to_llm = state['messages'] + [phase_prompt]
        response = agent.invoke(messages_to_llm)
        messages = [response]
        messages.extend(self._execute_tools(tool_calls=response.tool_calls))

        return Command(update={'messages': messages})

    def _execute_tools(self, tool_calls):
        """Execute tool calls and return formatted tool messages.

        Args:
            tool_calls: List of tool call dictionaries from LLM response.

        Returns:
            List of ToolMessage objects with execution results.
        """
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
        """Deduct operational cost from agent's cash.

        Called automatically at the end of each turn. If agent cannot pay,
        they go bankrupt.

        Returns:
            True if payment successful, False if agent is bankrupt.
        """
        if self.inventory.cash < self.config.operational_cost:
            self.inventory.cash = 0
            return False

        self.inventory.cash -= self.config.operational_cost
        return True
