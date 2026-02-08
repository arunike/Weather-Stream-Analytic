from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple
from enum import Enum
import logging
import math

logger = logging.getLogger(__name__)

class ManipulationType(Enum):
    PUMP_AND_DUMP = "pump_and_dump"
    WASH_TRADING = "wash_trading"
    SPOOFING = "spoofing"
    LAYERING = "layering"
    INSIDER_TRADING = "insider_trading"
    FRONT_RUNNING = "front_running"

class ManipulationSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class ManipulationAlert:
    is_manipulation: bool
    manipulation_type: ManipulationType
    severity: ManipulationSeverity
    confidence: float
    symbol: str
    reason: str
    evidence: List[str]
    estimated_impact: float  # 预估市场影响（美元）
    recommended_action: str
    metadata: Dict
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()

class MarketManipulationRule(ABC):
    def __init__(self, enabled: bool = True, priority: int = 0):
        self.enabled = enabled
        self.priority = priority
        self.name = self.__class__.__name__
    
    @abstractmethod
    def evaluate(self, trade: Dict, context: Dict) -> Optional[ManipulationAlert]:
        pass

class PumpAndDumpRule(MarketManipulationRule):
    def __init__(
        self,
        volume_spike_threshold: float = 5.0,  # 交易量为平均5倍
        price_surge_threshold: float = 0.30,  # 价格上涨30%
        social_hype_threshold: float = 10.0,  # 社交媒体提及量激增
        time_window_hours: int = 24,
        enabled: bool = True,
        priority: int = 10
    ):
        super().__init__(enabled, priority)
        self.volume_spike_threshold = volume_spike_threshold
        self.price_surge_threshold = price_surge_threshold
        self.social_hype_threshold = social_hype_threshold
        self.time_window_hours = time_window_hours
    
    def evaluate(self, trade: Dict, context: Dict) -> Optional[ManipulationAlert]:
        symbol = trade.get('symbol')
        current_price = trade.get('price', 0)
        current_volume = trade.get('volume', 0)
        timestamp = trade.get('timestamp')
        
        evidence = []
        manipulation_score = 0.0
        
        # 1. 检测交易量激增
        avg_volume = context.get('avg_volume_30d', current_volume)
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
        
        if volume_ratio >= self.volume_spike_threshold:
            manipulation_score += 0.25
            evidence.append(
                f"Trading volume {volume_ratio:.1f}x higher than 30-day average"
            )
        
        # 2. 检测价格快速上涨
        price_24h_ago = context.get('price_24h_ago', current_price)
        price_change_ratio = (current_price - price_24h_ago) / price_24h_ago if price_24h_ago > 0 else 0
        
        if price_change_ratio >= self.price_surge_threshold:
            manipulation_score += 0.30
            evidence.append(
                f"Price surged {price_change_ratio:.1%} in 24 hours"
            )
        
        # 3. 检测社交媒体活动
        social_mentions = context.get('social_media_mentions_24h', 0)
        avg_social_mentions = context.get('avg_social_mentions', 1)
        social_spike = social_mentions / avg_social_mentions if avg_social_mentions > 0 else 1
        
        if social_spike >= self.social_hype_threshold:
            manipulation_score += 0.20
            evidence.append(
                f"Social media mentions increased {social_spike:.1f}x"
            )
        
        # 4. 检测是否为小盘股/低流动性
        market_cap = context.get('market_cap', float('inf'))
        is_small_cap = market_cap < 300_000_000  # < $300M
        
        if is_small_cap:
            manipulation_score += 0.15
            evidence.append(
                f"Small-cap stock (market cap: ${market_cap/1e6:.1f}M)"
            )
        
        # 5. 检测买卖imbalance（大量买入）
        buy_sell_ratio = context.get('buy_sell_ratio', 1.0)
        if buy_sell_ratio > 3.0:  # 买入是卖出的3倍
            manipulation_score += 0.10
            evidence.append(
                f"Significant buy-sell imbalance (ratio: {buy_sell_ratio:.1f})"
            )
        
        # 6. 检查是否有已知的pump group参与
        known_pump_accounts = context.get('known_pump_accounts', set())
        trade_participants = set(trade.get('participants', []))
        
        if trade_participants.intersection(known_pump_accounts):
            manipulation_score += 0.30
            evidence.append("Known pump group participants involved")
        
        # 判定
        is_manipulation = manipulation_score >= 0.5
        
        if is_manipulation:
            severity = (
                ManipulationSeverity.CRITICAL if manipulation_score >= 0.8 else
                ManipulationSeverity.HIGH if manipulation_score >= 0.65 else
                ManipulationSeverity.MEDIUM
            )
            
            # 估算市场影响
            estimated_impact = (
                current_volume * current_price * 
                min(price_change_ratio, 1.0)
            )
            
            return ManipulationAlert(
                is_manipulation=True,
                manipulation_type=ManipulationType.PUMP_AND_DUMP,
                severity=severity,
                confidence=min(0.95, manipulation_score),
                symbol=symbol,
                reason=f"Pump and dump pattern detected (score: {manipulation_score:.2f})",
                evidence=evidence,
                estimated_impact=estimated_impact,
                recommended_action="Halt trading, investigate participants, alert SEC",
                metadata={
                    'manipulation_score': manipulation_score,
                    'volume_ratio': volume_ratio,
                    'price_change': price_change_ratio,
                    'social_spike': social_spike,
                    'market_cap': market_cap
                }
            )
        
        return None

class WashTradingRule(MarketManipulationRule):
    def __init__(
        self,
        price_tolerance: float = 0.01,  # 价格差异1%
        min_roundtrips: int = 3,
        time_window_minutes: int = 30,
        enabled: bool = True,
        priority: int = 9
    ):
        super().__init__(enabled, priority)
        self.price_tolerance = price_tolerance
        self.min_roundtrips = min_roundtrips
        self.time_window_minutes = time_window_minutes
    
    def evaluate(self, trade: Dict, context: Dict) -> Optional[ManipulationAlert]:
        symbol = trade.get('symbol')
        trader_id = trade.get('trader_id')
        price = trade.get('price', 0)
        side = trade.get('side')  # 'buy' or 'sell'
        
        evidence = []
        manipulation_score = 0.0
        
        # 获取该trader的近期交易
        trader_history = context.get('trader_recent_trades', [])
        cutoff_time = datetime.utcnow() - timedelta(minutes=self.time_window_minutes)
        
        recent_trades = [
            t for t in trader_history
            if t.get('timestamp') >= cutoff_time and
            t.get('symbol') == symbol
        ]
        
        # 1. 检测roundtrips（来回交易）
        roundtrips = self._detect_roundtrips(recent_trades, price)
        
        if len(roundtrips) >= self.min_roundtrips:
            manipulation_score += 0.40
            evidence.append(
                f"Detected {len(roundtrips)} roundtrip trades within "
                f"{self.time_window_minutes} minutes"
            )
        
        # 2. 检测关联账户（同一实体的多个账户）
        related_accounts = context.get('related_trader_accounts', {}).get(trader_id, [])
        
        # 检查是否在related accounts之间交易
        for rt in recent_trades:
            counterparty = rt.get('counterparty_id')
            if counterparty in related_accounts:
                manipulation_score += 0.35
                evidence.append(
                    f"Trading with related account: {counterparty}"
                )
                break
        
        # 3. 检测价格稳定性（wash trading通常价格不变）
        if recent_trades:
            prices = [t.get('price', 0) for t in recent_trades]
            price_variance = self._calculate_price_variance(prices)
            
            if price_variance < price * self.price_tolerance:
                manipulation_score += 0.15
                evidence.append(
                    f"Minimal price movement despite high volume "
                    f"(variance: {price_variance:.4f})"
                )
        
        # 4. 检测交易量与市场影响的不匹配
        volume = sum(t.get('volume', 0) for t in recent_trades)
        price_impact = context.get('price_impact', 0)
        
        # 大量交易但价格几乎不变
        if volume > 0 and price_impact < 0.005:  # <0.5%
            manipulation_score += 0.10
            evidence.append(
                f"High volume ({volume}) with minimal price impact ({price_impact:.2%})"
            )
        
        is_manipulation = manipulation_score >= 0.5
        
        if is_manipulation:
            severity = (
                ManipulationSeverity.HIGH if manipulation_score >= 0.7 else
                ManipulationSeverity.MEDIUM
            )
            
            return ManipulationAlert(
                is_manipulation=True,
                manipulation_type=ManipulationType.WASH_TRADING,
                severity=severity,
                confidence=min(0.90, manipulation_score),
                symbol=symbol,
                reason=f"Wash trading detected (score: {manipulation_score:.2f})",
                evidence=evidence,
                estimated_impact=volume * price,
                recommended_action="Suspend trader accounts, investigate related entities",
                metadata={
                    'manipulation_score': manipulation_score,
                    'roundtrips': len(roundtrips),
                    'trader_id': trader_id,
                    'related_accounts': related_accounts
                }
            )
        
        return None
    
    def _detect_roundtrips(self, trades: List[Dict], current_price: float) -> List[Tuple]:
        roundtrips = []
        
        # 简化：查找buy-sell或sell-buy配对
        for i, t1 in enumerate(trades):
            for t2 in trades[i+1:]:
                # 检查是否为反向交易
                if t1.get('side') != t2.get('side'):
                    # 检查价格是否接近
                    price1 = t1.get('price', 0)
                    price2 = t2.get('price', 0)
                    price_diff = abs(price1 - price2) / price1 if price1 > 0 else 0
                    
                    if price_diff <= self.price_tolerance:
                        roundtrips.append((t1, t2))
        
        return roundtrips
    
    @staticmethod
    def _calculate_price_variance(prices: List[float]) -> float:
        if len(prices) <= 1:
            return 0.0
        mean = sum(prices) / len(prices)
        variance = sum((p - mean) ** 2 for p in prices) / len(prices)
        return variance ** 0.5

class SpoofingRule(MarketManipulationRule):
    def __init__(
        self,
        cancel_ratio_threshold: float = 0.7,  # 70% of orders canceled
        order_size_ratio: float = 10.0,  # Order size is 10x average
        cancel_time_seconds: int = 60,  # Cancel within 60 seconds
        enabled: bool = True,
        priority: int = 9
    ):
        super().__init__(enabled, priority)
        self.cancel_ratio_threshold = cancel_ratio_threshold
        self.order_size_ratio = order_size_ratio
        self.cancel_time_seconds = cancel_time_seconds
    
    def evaluate(self, order: Dict, context: Dict) -> Optional[ManipulationAlert]:
        symbol = order.get('symbol')
        trader_id = order.get('trader_id')
        order_size = order.get('size', 0)
        order_type = order.get('type')  # 'limit', 'market'
        
        # Spoofing主要针对limit orders
        if order_type != 'limit':
            return None
        
        evidence = []
        manipulation_score = 0.0
        
        # 获取该trader的订单历史
        trader_orders = context.get('trader_order_history', [])
        recent_cutoff = datetime.utcnow() - timedelta(minutes=10)
        
        recent_orders = [
            o for o in trader_orders
            if o.get('timestamp') >= recent_cutoff and
            o.get('symbol') == symbol
        ]
        
        if len(recent_orders) < 5:
            return None  # 需要足够的历史数据
        
        # 1. 检测取消率
        canceled_orders = [o for o in recent_orders if o.get('status') == 'canceled']
        cancel_ratio = len(canceled_orders) / len(recent_orders)
        
        if cancel_ratio >= self.cancel_ratio_threshold:
            manipulation_score += 0.35
            evidence.append(
                f"High order cancellation rate: {cancel_ratio:.1%} "
                f"({len(canceled_orders)}/{len(recent_orders)})"
            )
        
        # 2. 检测快速取消
        rapid_cancels = []
        for order in canceled_orders:
            time_to_cancel = (
                order.get('cancel_time', datetime.utcnow()) - 
                order.get('timestamp')
            ).total_seconds()
            
            if time_to_cancel <= self.cancel_time_seconds:
                rapid_cancels.append(order)
        
        if len(rapid_cancels) >= 3:
            manipulation_score += 0.25
            evidence.append(
                f"{len(rapid_cancels)} orders canceled within "
                f"{self.cancel_time_seconds} seconds"
            )
        
        # 3. 检测异常大的订单size
        avg_order_size = context.get('avg_order_size', order_size)
        size_ratio = order_size / avg_order_size if avg_order_size > 0 else 1
        
        if size_ratio >= self.order_size_ratio:
            manipulation_score += 0.20
            evidence.append(
                f"Order size {size_ratio:.1f}x larger than average"
            )
        
        # 4. 检测订单簿imbalance（一边大量订单）
        bid_ask_imbalance = context.get('bid_ask_imbalance', 1.0)
        if bid_ask_imbalance > 5.0 or bid_ask_imbalance < 0.2:
            manipulation_score += 0.20
            evidence.append(
                f"Significant order book imbalance: {bid_ask_imbalance:.2f}"
            )
        
        is_manipulation = manipulation_score >= 0.5
        
        if is_manipulation:
            severity = (
                ManipulationSeverity.HIGH if manipulation_score >= 0.7 else
                ManipulationSeverity.MEDIUM
            )
            
            return ManipulationAlert(
                is_manipulation=True,
                manipulation_type=ManipulationType.SPOOFING,
                severity=severity,
                confidence=min(0.88, manipulation_score),
                symbol=symbol,
                reason=f"Spoofing behavior detected (score: {manipulation_score:.2f})",
                evidence=evidence,
                estimated_impact=order_size * order.get('price', 0) * 0.01,
                recommended_action="Issue warning, possible fine or suspension",
                metadata={
                    'manipulation_score': manipulation_score,
                    'cancel_ratio': cancel_ratio,
                    'rapid_cancels': len(rapid_cancels),
                    'trader_id': trader_id
                }
            )
        
        return None

class MarketManipulationEngine:
    def __init__(self):
        self.rules: List[MarketManipulationRule] = []
        self._initialize_default_rules()
        logger.info("Initialized Market Manipulation Detection Engine")
    
    def _initialize_default_rules(self):
        self.add_rule(PumpAndDumpRule())
        self.add_rule(WashTradingRule())
        self.add_rule(SpoofingRule())
    
    def add_rule(self, rule: MarketManipulationRule):
        self.rules.append(rule)
        self.rules.sort(key=lambda r: r.priority, reverse=True)
        logger.info(f"Added rule: {rule.name} (priority: {rule.priority})")
    
    def evaluate_trade(
        self,
        trade: Dict,
        context: Dict
    ) -> List[ManipulationAlert]:
        symbol = trade.get('symbol')
        logger.info(f"Evaluating trade for manipulation: {symbol}")
        
        alerts = []
        
        for rule in self.rules:
            if not rule.enabled:
                continue
            
            try:
                alert = rule.evaluate(trade, context)
                if alert and alert.is_manipulation:
                    alerts.append(alert)
                    logger.warning(
                        f"Manipulation alert: {rule.name} "
                        f"(type: {alert.manipulation_type.value}, "
                        f"confidence: {alert.confidence:.2f})"
                    )
            except Exception as e:
                logger.error(f"Error evaluating rule {rule.name}: {str(e)}")
        
        return alerts
    
    def get_most_severe_alert(
        self,
        alerts: List[ManipulationAlert]
    ) -> Optional[ManipulationAlert]:
        if not alerts:
            return None
        
        severity_order = {
            ManipulationSeverity.CRITICAL: 4,
            ManipulationSeverity.HIGH: 3,
            ManipulationSeverity.MEDIUM: 2,
            ManipulationSeverity.LOW: 1
        }
        
        return max(
            alerts,
            key=lambda a: (severity_order[a.severity], a.confidence)
        )
