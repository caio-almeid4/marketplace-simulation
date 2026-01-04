from random import shuffle
from typing import List, Optional

from loguru import logger

from models.agent import Agent
from models.market import Market
from schemas.message import Message
from schemas.simulation import SimulationSettings
from schemas.trade import UnitTrade
from services.broadcast_service import BroadcastService
from services.inventory_service import InventoryService
from settings import general_settings
from utils.tools_factory import create_trade_tools


class Simulation:
    """Main simulation orchestrator for the marketplace.

    Coordinates all simulation activities including agent turns, market operations,
    energy/cash management, inventory tracking, and event broadcasts across multiple
    rounds.

    Attributes:
        simulation_settings: Configuration for rounds and other simulation parameters.
        agents: List of all agents participating in the simulation.
        market: The central market authority managing trades.
        bankrupt: List of agents who ran out of cash.
        dead: List of agents who ran out of energy.
        inventory_service: Optional service for database persistence of snapshots.
        broadcast_service: Optional service for random market events.
    """

    def __init__(
        self,
        settings: SimulationSettings,
        agents: List[Agent],
        market: Market,
        inventory_service: Optional[InventoryService] = None,
        broadcast_service: Optional[BroadcastService] = None,
    ):
        """Initialize the Simulation.

        Args:
            settings: Simulation configuration (rounds, etc.).
            agents: List of agents to participate.
            market: Market instance for managing trades.
            inventory_service: Optional service for tracking inventory history.
            broadcast_service: Optional service for broadcasting events.
        """
        self.simulation_settings = settings
        self.agents = agents
        self.market = market
        self.bankrupt: List[Agent] = []
        self.dead: List[Agent] = []
        self.inventory_service = inventory_service
        self.broadcast_service = broadcast_service
        self.round_metrics = {}

    def run(self):
        """Execute the full simulation for the configured number of rounds.

        Main loop that:
        1. Filters dead agents
        2. Shuffles agent turn order
        3. Broadcasts events
        4. Runs each agent's turn
        5. Collects operational costs
        6. Drains energy and handles deaths
        7. Snapshots inventories
        8. Logs round summary
        """
        self._provide_tools()
        agents_queue = self.agents.copy()
        total_rounds = self.simulation_settings.rounds

        for i in range(1, total_rounds + 1):
            agents_queue = [agent for agent in agents_queue if agent.is_alive]
            shuffle(agents_queue)

            self._log_round_header(i, len(agents_queue), total_rounds)
            self._broadcast_event(agents_queue)
            
            trades_before = len(self.market.get_trade_history())
            for agent in agents_queue:
                self._log_agent_turn(agent)
                market_data = self.market.get_market_data()
                agent.run_turn(market_data=market_data, round_num=i)
                self._collect_agent_payment(agent)

            self._drain_energy(agents_queue)
            self._snapshot_inventories(round_number=i)

            trades_this_round = len(self.market.get_trade_history()) - trades_before
            self._log_round_summary(i, trades_this_round, len(self.market._repository))
            self._save_round_metrics(
                round_num=i, 
                round_trade_history=self.market.get_trade_history()[-trades_this_round:]
            )

    def _provide_tools(self) -> None:
        """Inject trading tools into each agent.

        Creates and binds the market-specific tools (create_offer, accept_offer,
        etc.) to each agent before simulation starts.
        """
        for agent in self.agents:
            agent.tools = create_trade_tools(agent, self.market)

    def _collect_agent_payment(self, agent: Agent) -> None:
        """Collect operational cost from agent after their turn.

        If agent cannot pay, marks them as bankrupt, deletes their offers,
        and adds them to the bankrupt list.

        Args:
            agent: The agent to collect payment from.
        """
        if not agent.collect_operational_payment():
            agent.is_alive = False
            self.market.delete_agent_offers(agent.name)
            self.bankrupt.append(agent)
            logger.warning(f'     BANKRUPT: {agent.name.upper()} ran out of cash!')

    def _drain_energy(self, agents: List[Agent]) -> None:
        """Drain energy from all agents and handle deaths.

        Automatically consumes apples when energy drops below threshold.
        If energy reaches zero, agent dies and their offers are deleted.

        Args:
            agents: List of agents to drain energy from.
        """
        for agent in agents:
            agent.energy -= 1
            if agent.energy == 0:
                agent.is_alive = False
                self.market.delete_agent_offers(agent.name)
                self.dead.append(agent)
                logger.warning(f'     DIED: {agent.name.upper()} ran out of energy!')

            if (
                agent.energy < general_settings.energy_qty_to_consume_apple
                and agent.inventory.apple
            ):
                agent.energy += general_settings.energy_qty_restored_by_apple
                agent.inventory.apple -= 1

    def _snapshot_inventories(self, round_number: int) -> None:
        """Save inventory snapshots to database for all agents.

        Args:
            round_number: Current round number for the snapshot.
        """
        if self.inventory_service:
            self.inventory_service.create_all_snapshots(self.agents, round_number)
            logger.debug(f'Inventory snapshots created for round {round_number}')

    def _broadcast_event(self, agents: List[Agent]) -> None:
        """Broadcast a random market event to all agents.

        If broadcast service is available, fetches a random event and sends
        it to all agents' inboxes.

        Args:
            agents: List of agents to receive the broadcast.
        """
        if not self.broadcast_service:
            return
        event = self.broadcast_service.get_random_event()
        if event:
            broadcast_msg = Message(
                sender='MARKET_NEWS',
                content=f'[{event.category.upper()}] {event.title}: {event.content}',
            )
            for agent in agents:
                agent.inbox.append(broadcast_msg)
            logger.info(f'  NEWS: {event.title}')

    @staticmethod
    def _log_round_header(round_num: int, agent_count: int, total: int) -> None:
        """Log the round header with formatting.

        Args:
            round_num: Current round number.
            agent_count: Number of living agents.
            total: Total rounds in simulation.
        """
        header = f' ROUND {round_num}/{total} ({agent_count} agents) '
        logger.info(f'\n{"─" * 50}')
        logger.info(f'{header.center(50, "─")}')
        logger.info(f'{"─" * 50}')

    @staticmethod
    def _log_round_summary(round_num: int, trades: int, active_offers: int) -> None:
        """Log the round summary with trade and offer counts.

        Args:
            round_num: Current round number.
            trades: Number of trades executed this round.
            active_offers: Number of active offers remaining.
        """
        logger.info(
            f'\n  Round {round_num} Summary: {trades} trades | {active_offers} offers'
        )

    @staticmethod
    def _log_agent_turn(agent: Agent) -> None:
        """Log agent's current state at the start of their turn.

        Args:
            agent: The agent whose turn is starting.
        """
        inv = agent.inventory
        logger.info(
            f'\n  >> {agent.name.upper()} | '
            f'${inv.cash:.0f} | '
            f'A:{inv.apple} C:{inv.chip} G:{inv.gold} | '
            f'E:{agent.energy}'
        )

    def _save_round_metrics(self, round_num: int, round_trade_history: List[UnitTrade]):
        
        metrics = {}
        items = ['apple', 'chip', 'gold']
        items_info = {
            item: [0.0, 0] for item in items
        }
        for trade in round_trade_history:
            items_info[trade.item][0] += trade.price
            items_info[trade.item][1] += 1
            
        
        items_average_price = {
            item: info[0] / info[1] for item, info in items_info.items()
        }
        
        metrics['item_average_price'] = items_average_price
        self.round_metrics[round_num] = metrics