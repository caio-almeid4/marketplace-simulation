from random import shuffle
from typing import Dict

from loguru import logger

from models.agent import Agent
from models.market import Market
from schemas.simulation import SimulationSettings
from utils.tools_factory import create_trade_tools


class Simulation:
    def __init__(
        self, settings: SimulationSettings, agents: Dict[str, Agent], market: Market
    ):
        self.simulation_settings = settings
        self.agents = agents
        self.market = market

    def run(self):

        self._provide_tools()
        agents_queue = [name for name in self.agents.keys()]
        for i in range(1, self.simulation_settings.rounds + 1):
            logger.info(f'----ROUND {i}----')
            shuffle(agents_queue)
            for agent in agents_queue:
                logger.info(f'{agent.upper()} turn')
                market_data = self.market.format_repository()
                self.agents[agent].run_turn(market_data=market_data, round_num=i)

            if i % 2 == 0:
                self.market.clear_repository()

    def _provide_tools(self) -> None:

        for agent in self.agents.values():
            agent.tools = create_trade_tools(agent, self.market)
