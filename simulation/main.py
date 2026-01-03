from random import shuffle
from typing import List

from loguru import logger

from models.agent import Agent
from models.market import Market
from schemas.simulation import SimulationSettings
from utils.tools_factory import create_trade_tools


class Simulation:
    def __init__(
        self, settings: SimulationSettings, agents: List[Agent], market: Market
    ):
        self.simulation_settings = settings
        self.agents = agents
        self.market = market
        self.bankrupt: List[Agent] = []
        self.dead: List[Agent] = []
        
    def run(self):

        self._provide_tools()
        agents_queue = self.agents.copy()
        for i in range(1, self.simulation_settings.rounds + 1):
            agents_queue = [agent for agent in agents_queue if agent.is_alive]
            shuffle(agents_queue)
            logger.info(f'----ROUND {i}----')
            for agent in agents_queue:
                logger.info(f'{agent.name.upper()} turn')
                market_data = self.market.get_market_data()
                agent.run_turn(market_data=market_data, round_num=i)
                self._collect_agent_payment(agent)
        
            self._drain_energy(agents_queue)
            #if i % 2 == 0:
            #    self.market.clear_repository()

    def _provide_tools(self) -> None:

        for agent in self.agents:
            agent.tools = create_trade_tools(agent, self.market)
    
    def _collect_agent_payment(self, agent: Agent) -> None:
        if not agent.collect_operational_payment():
            agent.is_alive = False
            self.market.delete_agent_offers(agent.name)
            self.bankrupt.append(agent)
            logger.info(f'{agent.name.upper()} bankrupted')

            
    def _drain_energy(self, agents: List[Agent]) -> None:
        
        for agent in agents:
            agent.energy -= 1
            if agent.energy == 0:
                agent.is_alive = False
                self.market.delete_agent_offers(agent.name)
                self.dead.append(agent)
                logger.info(f'{agent.name.upper()} died')
                
            if agent.energy < 5 and agent.inventory.apple:
                agent.energy += 3
                agent.inventory.apple -= 1
