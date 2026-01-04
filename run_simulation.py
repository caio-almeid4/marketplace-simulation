import argparse
import sys
from typing import Dict

from dotenv import load_dotenv
from loguru import logger

from db import create_tables, get_db_session
from models.agent import Agent
from models.market import Market
from schemas.simulation import SimulationSettings
from services.broadcast_service import BroadcastService
from services.inventory_service import InventoryService
from services.plot_service import PlotService
from services.trade_service import TradeService
from simulation import Simulation
from utils.agent_config import get_agents_configs
from utils.id_generator import SerialIDGenerator


def configure_logger() -> None:
    """Configure loguru logger for clean, colorized console output.

    Removes default handlers and adds a custom format without timestamps
    for better readability during simulation.
    """
    logger.remove()
    logger.add(
        sys.stdout,
        format='<level>{message}</level>',
        level='INFO',
        colorize=True,
    )


def print_banner(
    text: str, agent_count: int | None = None, stats: Dict[str, int] | None = None
) -> None:
    """Print a formatted banner for simulation start/end.

    Args:
        text: Main banner text to display.
        agent_count: Optional number of agents to display.
        stats: Optional dictionary with survivors, bankrupt, and dead counts.
    """
    width = 44
    logger.info(f'\n{"=" * width}')
    logger.info(f'{text.center(width)}')
    if agent_count is not None:
        logger.info(f'{f"{agent_count} agents loaded".center(width)}')
    if stats:
        stats_line = f'Survivors: {stats["survivors"]} | Bankrupt: {stats["bankrupt"]} | Dead: {stats["dead"]}'
        logger.info(f'{stats_line.center(width)}')
    logger.info(f'{"=" * width}\n')


def main(rounds: int) -> None:
    """Main entry point for the marketplace simulation.

    Sets up database, loads agent configurations, creates services,
    runs the simulation, and displays final results.

    Args:
        rounds: Number of simulation rounds to execute.
    """
    configure_logger()
    load_dotenv()
    create_tables()

    agents_configs = get_agents_configs(['*'])
    agents = {name: Agent(config) for name, config in agents_configs.items()}
    id_gen = SerialIDGenerator()

    print_banner('MARKETPLACE SIMULATION START', agent_count=len(agents))

    with get_db_session() as session:
        trade_service = TradeService(session=session)
        inventory_service = InventoryService(session=session)
        broadcast_service = BroadcastService()
        market = Market(agents=agents, id_gen=id_gen, trade_service=trade_service)
        sim_settings = SimulationSettings(rounds=rounds)
        sim = Simulation(
            settings=sim_settings,
            agents=list(agents.values()),
            market=market,
            inventory_service=inventory_service,
            broadcast_service=broadcast_service,
        )
        sim.run()

        survivors = len([a for a in agents.values() if a.is_alive])
        stats = {
            'survivors': survivors,
            'bankrupt': len(sim.bankrupt),
            'dead': len(sim.dead),
        }
        print_banner(f'SIMULATION COMPLETE ({rounds} rounds)', stats=stats)

        # Generate analytics plots
        plot_service = PlotService(session=session)
        plot_service.generate_all_plots(output_dir='plots/')
        logger.info('Generated simulation plots in plots/ directory')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Simulation configs')
    parser.add_argument('--rounds', default=20, type=int)
    args = parser.parse_args()
    main(**vars(args))
