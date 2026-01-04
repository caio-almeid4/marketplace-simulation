import os
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
from loguru import logger
from sqlalchemy import func
from sqlalchemy.orm import Session

from schemas.inventory_history import InventorySnapshot
from schemas.trade import Trade


class PlotService:
    """Service for generating simulation analytics visualizations.

    Creates 5 key plots from database data:
    1. Price trends - average price per item per round
    2. Net worth bump chart - agent rankings over time
    3. Energy-price correlation - system-wide averages
    4. Volume vs cash - transaction activity vs final wealth
    5. Asset composition - portfolio breakdown per agent

    Attributes:
        session: SQLAlchemy database session for querying data.
    """

    def __init__(self, session: Session):
        """Initialize the PlotService.

        Args:
            session: Active database session for data queries.
        """
        self.session = session
        sns.set_theme(style='whitegrid', palette='husl')

    def get_price_trends(self) -> Dict[str, List[Tuple[int, float]]]:
        """Query average unit price per item per round.

        Returns:
            Dictionary mapping item names to lists of (round, avg_price) tuples.
            Example: {'apple': [(1, 5.2), (2, 5.5)], 'chip': [...], 'gold': [...]}
        """
        result = (
            self.session.query(
                Trade.item,
                Trade.round_number,
                func.avg(Trade.price / Trade.quantity).label('avg_unit_price'),
            )
            .group_by(Trade.item, Trade.round_number)
            .order_by(Trade.round_number, Trade.item)
            .all()
        )

        price_trends = {}
        for item, round_num, avg_price in result:
            if item not in price_trends:
                price_trends[item] = []
            price_trends[item].append((round_num, avg_price))

        return price_trends

    def get_net_worth_data(self) -> Dict[str, List[Tuple[int, float]]]:
        """Calculate net worth per agent per round using market prices.

        Net worth = cash + (items × average_market_price_that_round)

        Returns:
            Dictionary mapping agent names to lists of (round, net_worth) tuples.
        """
        price_trends = self.get_price_trends()

        # Build price lookup: {round: {item: price}}
        price_by_round = {}
        for item, rounds_data in price_trends.items():
            for round_num, avg_price in rounds_data:
                if round_num not in price_by_round:
                    price_by_round[round_num] = {}
                price_by_round[round_num][item] = avg_price

        # Query all inventory snapshots
        snapshots = (
            self.session.query(InventorySnapshot)
            .order_by(InventorySnapshot.round_number, InventorySnapshot.agent_name)
            .all()
        )

        net_worth_data = {}
        for snapshot in snapshots:
            if snapshot.agent_name not in net_worth_data:
                net_worth_data[snapshot.agent_name] = []

            # Calculate net worth
            net_worth = snapshot.cash
            prices = price_by_round.get(snapshot.round_number, {})
            net_worth += snapshot.apple * prices.get('apple', 0)
            net_worth += snapshot.chip * prices.get('chip', 0)
            net_worth += snapshot.gold * prices.get('gold', 0)

            net_worth_data[snapshot.agent_name].append(
                (snapshot.round_number, net_worth)
            )

        return net_worth_data

    def get_energy_price_correlation(self) -> List[Tuple[int, float, float]]:
        """Query system-wide average energy and apple price per round.

        Returns:
            List of (round_number, avg_energy, avg_apple_price) tuples.
            One data point per round showing system-wide averages.
        """
        # Get average energy per round
        energy_by_round = {}
        energy_result = (
            self.session.query(
                InventorySnapshot.round_number,
                func.avg(InventorySnapshot.energy).label('avg_energy'),
            )
            .group_by(InventorySnapshot.round_number)
            .all()
        )
        for round_num, avg_energy in energy_result:
            energy_by_round[round_num] = avg_energy

        # Get average apple price per round
        apple_price_result = (
            self.session.query(
                Trade.round_number,
                func.avg(Trade.price / Trade.quantity).label('avg_apple_price'),
            )
            .filter(Trade.item == 'apple')
            .group_by(Trade.round_number)
            .all()
        )

        correlation_data = []
        for round_num, avg_apple_price in apple_price_result:
            avg_energy = energy_by_round.get(round_num)
            if avg_energy is not None:
                correlation_data.append((round_num, avg_energy, avg_apple_price))

        return correlation_data

    def get_volume_vs_cash(self) -> List[Tuple[str, int, float]]:
        """Query transaction volume and final cash balance per agent.

        Returns:
            List of (agent_name, transaction_volume, final_cash) tuples.
        """
        # Get max round number
        max_round = self.session.query(func.max(InventorySnapshot.round_number)).scalar()

        if max_round is None:
            return []

        # Get final cash balances
        final_cash_by_agent = {}
        final_snapshots = (
            self.session.query(InventorySnapshot)
            .filter(InventorySnapshot.round_number == max_round)
            .all()
        )
        for snapshot in final_snapshots:
            final_cash_by_agent[snapshot.agent_name] = snapshot.cash

        # Count transaction volume per agent (as buyer or supplier)
        volume_data = []
        for agent_name, final_cash in final_cash_by_agent.items():
            volume = (
                self.session.query(func.count(Trade.id))
                .filter(
                    (Trade.buyer == agent_name) | (Trade.supplier == agent_name)
                )
                .scalar()
            )
            volume_data.append((agent_name, volume, final_cash))

        return volume_data

    def get_asset_composition(self) -> Dict[str, Dict[str, float]]:
        """Query final asset composition percentages per agent.

        Returns:
            Dictionary mapping agent names to percentage breakdowns.
            Example: {'agent1': {'apple': 30.5, 'chip': 45.2, 'gold': 24.3}}
        """
        max_round = self.session.query(func.max(InventorySnapshot.round_number)).scalar()

        if max_round is None:
            return {}

        final_snapshots = (
            self.session.query(InventorySnapshot)
            .filter(InventorySnapshot.round_number == max_round)
            .all()
        )

        composition_data = {}
        for snapshot in final_snapshots:
            total_items = snapshot.apple + snapshot.chip + snapshot.gold
            if total_items > 0:
                composition_data[snapshot.agent_name] = {
                    'apple': (snapshot.apple / total_items) * 100,
                    'chip': (snapshot.chip / total_items) * 100,
                    'gold': (snapshot.gold / total_items) * 100,
                }
            else:
                # Agent has no items
                composition_data[snapshot.agent_name] = {
                    'apple': 0,
                    'chip': 0,
                    'gold': 0,
                }

        return composition_data

    def plot_price_trends(self, output_dir: str = 'plots/') -> None:
        """Create line chart showing average price per item per round.

        Args:
            output_dir: Directory to save the plot.
        """
        price_trends = self.get_price_trends()

        if not price_trends:
            logger.warning('No price trend data available to plot')
            return

        plt.figure(figsize=(10, 6))

        for item, data in price_trends.items():
            rounds = [r for r, _ in data]
            prices = [p for _, p in data]
            plt.plot(rounds, prices, marker='o', label=item.capitalize(), linewidth=2)

        plt.xlabel('Round Number', fontsize=12)
        plt.ylabel('Average Unit Price ($)', fontsize=12)
        plt.title('Item Price Trends Over Time', fontsize=14, fontweight='bold')
        plt.legend(title='Item', fontsize=10)
        plt.grid(True, alpha=0.3)
        plt.tight_layout()

        os.makedirs(output_dir, exist_ok=True)
        plt.savefig(f'{output_dir}/price_trends.png', dpi=300, bbox_inches='tight')
        plt.close()
        logger.info(f'Saved price trends plot to {output_dir}/price_trends.png')

    def plot_net_worth_bump_chart(self, output_dir: str = 'plots/') -> None:
        """Create bump chart showing agent net worth rankings over time.

        Args:
            output_dir: Directory to save the plot.
        """
        net_worth_data = self.get_net_worth_data()

        if not net_worth_data:
            logger.warning('No net worth data available to plot')
            return

        # Convert to rankings
        # First, organize by round
        rounds_data = {}
        for agent, data in net_worth_data.items():
            for round_num, net_worth in data:
                if round_num not in rounds_data:
                    rounds_data[round_num] = {}
                rounds_data[round_num][agent] = net_worth

        # Calculate rankings for each round
        rankings = {}
        for round_num, agents_worth in sorted(rounds_data.items()):
            sorted_agents = sorted(
                agents_worth.items(), key=lambda x: x[1], reverse=True
            )
            for rank, (agent, _) in enumerate(sorted_agents, 1):
                if agent not in rankings:
                    rankings[agent] = []
                rankings[agent].append((round_num, rank))

        plt.figure(figsize=(12, 8))

        for agent, data in rankings.items():
            rounds = [r for r, _ in data]
            ranks = [rank for _, rank in data]
            plt.plot(rounds, ranks, marker='o', label=agent, linewidth=2, markersize=8)

        plt.xlabel('Round Number', fontsize=12)
        plt.ylabel('Rank (1 = Highest Net Worth)', fontsize=12)
        plt.title('Agent Net Worth Rankings Over Time', fontsize=14, fontweight='bold')
        plt.gca().invert_yaxis()  # Rank 1 at top
        plt.legend(title='Agent', fontsize=9, bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.grid(True, alpha=0.3)
        plt.tight_layout()

        os.makedirs(output_dir, exist_ok=True)
        plt.savefig(f'{output_dir}/net_worth_bump_chart.png', dpi=300, bbox_inches='tight')
        plt.close()
        logger.info(f'Saved net worth bump chart to {output_dir}/net_worth_bump_chart.png')

    def plot_energy_price_correlation(self, output_dir: str = 'plots/') -> None:
        """Create scatter plot showing correlation between energy and apple price.

        Args:
            output_dir: Directory to save the plot.
        """
        correlation_data = self.get_energy_price_correlation()

        if not correlation_data:
            logger.warning('No energy-price correlation data available to plot')
            return

        rounds = [r for r, _, _ in correlation_data]
        energies = [e for _, e, _ in correlation_data]
        prices = [p for _, _, p in correlation_data]

        plt.figure(figsize=(10, 6))
        plt.scatter(energies, prices, s=100, alpha=0.6, edgecolors='black')

        # Add trend line
        if len(energies) > 1:
            z = np.polyfit(energies, prices, 1)
            p = np.poly1d(z)
            plt.plot(
                energies,
                p(energies),
                'r--',
                alpha=0.8,
                linewidth=2,
                label=f'Trend: y={z[0]:.2f}x+{z[1]:.2f}',
            )

            # Calculate correlation coefficient
            correlation = np.corrcoef(energies, prices)[0, 1]
            plt.text(
                0.05,
                0.95,
                f'Correlation: {correlation:.3f}',
                transform=plt.gca().transAxes,
                fontsize=11,
                verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5),
            )

        plt.xlabel('Average Energy (System-wide)', fontsize=12)
        plt.ylabel('Average Apple Price ($)', fontsize=12)
        plt.title('Energy-Price Correlation', fontsize=14, fontweight='bold')
        plt.legend(fontsize=10)
        plt.grid(True, alpha=0.3)
        plt.tight_layout()

        os.makedirs(output_dir, exist_ok=True)
        plt.savefig(
            f'{output_dir}/energy_price_correlation.png', dpi=300, bbox_inches='tight'
        )
        plt.close()
        logger.info(f'Saved energy-price correlation plot to {output_dir}/energy_price_correlation.png')

    def plot_volume_vs_cash(self, output_dir: str = 'plots/') -> None:
        """Create scatter plot showing transaction volume vs final cash balance.

        Args:
            output_dir: Directory to save the plot.
        """
        volume_data = self.get_volume_vs_cash()

        if not volume_data:
            logger.warning('No volume vs cash data available to plot')
            return

        agents = [agent for agent, _, _ in volume_data]
        volumes = [vol for _, vol, _ in volume_data]
        cash = [c for _, _, c in volume_data]

        plt.figure(figsize=(10, 6))
        plt.scatter(volumes, cash, s=150, alpha=0.6, edgecolors='black')

        # Label points with agent names
        for agent, vol, cash_val in volume_data:
            plt.annotate(
                agent,
                (vol, cash_val),
                xytext=(5, 5),
                textcoords='offset points',
                fontsize=9,
                alpha=0.8,
            )

        plt.xlabel('Transaction Volume (Number of Trades)', fontsize=12)
        plt.ylabel('Final Cash Balance ($)', fontsize=12)
        plt.title('Transaction Volume vs Final Cash Balance', fontsize=14, fontweight='bold')
        plt.grid(True, alpha=0.3)
        plt.tight_layout()

        os.makedirs(output_dir, exist_ok=True)
        plt.savefig(f'{output_dir}/volume_vs_cash.png', dpi=300, bbox_inches='tight')
        plt.close()
        logger.info(f'Saved volume vs cash plot to {output_dir}/volume_vs_cash.png')

    def plot_asset_composition(self, output_dir: str = 'plots/') -> None:
        """Create stacked bar chart showing asset composition per agent.

        Args:
            output_dir: Directory to save the plot.
        """
        composition_data = self.get_asset_composition()

        if not composition_data:
            logger.warning('No asset composition data available to plot')
            return

        agents = list(composition_data.keys())
        apple_pcts = [composition_data[agent]['apple'] for agent in agents]
        chip_pcts = [composition_data[agent]['chip'] for agent in agents]
        gold_pcts = [composition_data[agent]['gold'] for agent in agents]

        fig, ax = plt.subplots(figsize=(10, 6))

        # Create stacked horizontal bars
        ax.barh(agents, apple_pcts, label='Apple', color='#ff9999')
        ax.barh(agents, chip_pcts, left=apple_pcts, label='Chip', color='#66b3ff')
        ax.barh(
            agents,
            gold_pcts,
            left=[a + c for a, c in zip(apple_pcts, chip_pcts)],
            label='Gold',
            color='#ffd700',
        )

        ax.set_xlabel('Percentage of Assets (%)', fontsize=12)
        ax.set_ylabel('Agent Name', fontsize=12)
        ax.set_title('Final Asset Composition by Agent', fontsize=14, fontweight='bold')
        ax.legend(title='Item', fontsize=10)
        ax.set_xlim(0, 100)
        plt.grid(axis='x', alpha=0.3)
        plt.tight_layout()

        os.makedirs(output_dir, exist_ok=True)
        plt.savefig(f'{output_dir}/asset_composition.png', dpi=300, bbox_inches='tight')
        plt.close()
        logger.info(f'Saved asset composition plot to {output_dir}/asset_composition.png')

    def generate_all_plots(self, output_dir: str = 'plots/') -> None:
        """Generate all 5 simulation plots.

        Args:
            output_dir: Directory to save all plots (default: 'plots/').
        """
        logger.info('Generating simulation analytics plots...')
        os.makedirs(output_dir, exist_ok=True)

        self.plot_price_trends(output_dir)
        self.plot_net_worth_bump_chart(output_dir)
        self.plot_energy_price_correlation(output_dir)
        self.plot_volume_vs_cash(output_dir)
        self.plot_asset_composition(output_dir)

        logger.success(f'All plots generated successfully in {output_dir}')
