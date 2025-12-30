from random import shuffle
from typing import Dict

from models.agent import Agent
from models.market import Market
from schemas.inventory import Inventory
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

        for i in range(self.simulation_settings.rounds):
            shuffle(agents_queue)
            
            for agent in agents_queue:

                market_data = self.market.format_public_board()
                self.agents[agent].run_turn(market_data=market_data)
            print(self.market.public_board)

    def get_agent_inventory(self, agent_name: str) -> Inventory:

        agent_state = self.agents[agent_name].state
        inventory = Inventory(
            cash=agent_state["cash"],
            apple=agent_state["apple"],
            chip=agent_state["chip"],
            gold=agent_state["gold"],
        )

        return inventory

    def _provide_tools(self) -> None:

        for agent in self.agents.values():
            agent.tools = create_trade_tools(agent, self.market)
