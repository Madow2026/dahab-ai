"""
Forecasting Engine
Generates probabilistic forecasts from news analysis
"""

from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import json
import config

class Forecaster:
    """Generates probabilistic market forecasts"""
    
    def generate_forecasts(self, news_item: Dict, analysis: Dict, current_prices: Dict) -> List[Dict]:
        """
        Generate forecasts for all affected assets
        Returns list of forecast dicts
        """
        forecasts = []
        
        affected_assets = analysis['affected_assets']
        
        for asset in affected_assets:
            price_data = current_prices.get(asset, {})

            if getattr(config, 'ENABLE_MULTI_HORIZON_RECOMMENDATIONS', False):
                for horizon_key, horizon_minutes in (config.RECOMMENDATION_HORIZONS or {}).items():
                    forecast = self._create_forecast(
                        news_item,
                        analysis,
                        asset,
                        price_data,
                        horizon_minutes=int(horizon_minutes),
                        horizon_key=str(horizon_key),
                    )
                    forecasts.append(forecast)
            else:
                forecast = self._create_forecast(
                    news_item, analysis, asset, price_data
                )
                forecasts.append(forecast)
        
        return forecasts
    
    def _create_forecast(
        self,
        news_item: Dict,
        analysis: Dict,
        asset: str,
        price_data,
        horizon_minutes: int = None,
        horizon_key: str = None,
    ) -> Dict:
        """Create single forecast for asset"""
        category = analysis['category']
        sentiment = analysis['sentiment']
        impact_level = analysis['impact_level']
        base_confidence = analysis['confidence']
        
        # Determine direction and adjust confidence
        direction, confidence = self._determine_direction(
            category, sentiment, asset, base_confidence
        )

        # Required rule: never skip LOW impact; cap confidence instead
        confidence = self._cap_confidence_by_impact(confidence, impact_level)
        
        # Determine time horizon
        if horizon_minutes is None:
            horizon_minutes = config.FORECAST_HORIZONS.get(category, 240)
        
        # Determine risk level
        risk_level = self._determine_risk_level(confidence, impact_level)
        
        # Generate reasoning
        reasoning = self._generate_reasoning(category, sentiment, asset, direction)
        
        # Generate scenarios
        scenario_base, scenario_alt = self._generate_scenarios(
            asset, direction, category, sentiment
        )
        
        # Timestamps
        created_at = datetime.now()
        due_at = created_at + timedelta(minutes=horizon_minutes)
        
        # Get current price (accept dict or float)
        if isinstance(price_data, dict):
            current_price = price_data.get('price')
        else:
            current_price = price_data

        predicted_price = None
        try:
            if current_price is not None and str(current_price) != '':
                predicted_price = self._predict_price(
                    float(current_price),
                    direction=str(direction).upper(),
                    confidence=float(confidence),
                    horizon_minutes=int(horizon_minutes),
                    asset=str(asset),
                )
        except Exception:
            predicted_price = None

        reasoning_tags = {
            'category': category,
            'sentiment': sentiment,
            'impact_level': impact_level,
            'asset': asset,
            'horizon_key': horizon_key,
        }
        
        return {
            'news_id': news_item.get('id'),
            'asset': asset,
            'direction': direction,
            'confidence': confidence,
            'risk_level': risk_level,
            'horizon_minutes': horizon_minutes,
            'horizon_key': horizon_key,
            'created_at': created_at.isoformat(),
            'due_at': due_at.isoformat(),
            'reasoning': reasoning,
            'scenario_base': scenario_base,
            'scenario_alt': scenario_alt,
            'price_at_forecast': current_price
            ,'predicted_price': predicted_price
            ,'reasoning_tags': json.dumps(reasoning_tags, ensure_ascii=False)
            ,'news_category': category
            ,'news_sentiment': sentiment
            ,'impact_level': impact_level
        }

    def _predict_price(self, current_price: float, direction: str, confidence: float, horizon_minutes: int, asset: str) -> float:
        """Simple, deterministic price projection for storage + later evaluation.

        This is intentionally conservative and purely statistical (no retraining).
        """
        if current_price <= 0:
            return current_price

        asset_key = (asset or '').strip()
        # Rough daily move scale (percent). Keeps projections realistic.
        daily_move_pct = {
            'USD Index': 0.4,
            'Gold': 1.0,
            'Silver': 1.4,
            'Oil': 2.0,
            'Bitcoin': 4.5,
        }.get(asset_key, 1.0)

        days = max(float(horizon_minutes) / (60.0 * 24.0), 1.0 / (60.0 * 24.0))
        # Scale with sqrt(time) so 7d isn't 7x 1d.
        scaled_move = daily_move_pct * (days ** 0.5)

        sign = 0.0
        d = (direction or '').upper()
        if d == 'UP':
            sign = 1.0
        elif d == 'DOWN':
            sign = -1.0
        else:
            sign = 0.0

        conf_scale = max(0.0, min(float(confidence) / 100.0, 1.0))
        expected_pct = sign * scaled_move * (0.35 + 0.65 * conf_scale)

        projected = current_price * (1.0 + expected_pct / 100.0)
        # Round for stable display/storage.
        return round(projected, 4)

    def _cap_confidence_by_impact(self, confidence: float, impact_level: str) -> float:
        """Apply impact-based confidence caps.

        Requirement:
        - LOW => max 55%
        - MEDIUM => max 75%
        - HIGH => max 85%
        """
        level = (impact_level or '').strip().upper()
        if level == 'LOW':
            cap = 55.0
        elif level == 'MEDIUM':
            cap = 75.0
        elif level == 'HIGH':
            cap = 85.0
        else:
            cap = config.MAX_CONFIDENCE_ALLOWED

        capped = min(float(confidence), cap)
        capped = max(config.MIN_CONFIDENCE_ALLOWED, min(capped, config.MAX_CONFIDENCE_ALLOWED))
        return round(capped, 1)
    
    def _determine_direction(self, category: str, sentiment: str, asset: str, 
                            base_confidence: float) -> Tuple[str, float]:
        """Determine forecast direction and confidence"""
        from engine.impact_engine import ImpactEngine
        
        # Get correlation
        correlations = ImpactEngine.CORRELATIONS.get(category, {})
        correlation_data = correlations.get(asset)
        
        if not correlation_data:
            return 'NEUTRAL', max(base_confidence * 0.7, config.MIN_CONFIDENCE_ALLOWED)
        
        correlation_type, correlation_strength = correlation_data
        
        # Adjust confidence by correlation strength (less punitive than direct multiplication)
        # correlation_strength in [0..1] => multiplier in [0.5..1.0]
        multiplier = 0.5 + 0.5 * float(correlation_strength)
        confidence = float(base_confidence) * multiplier
        
        # Determine direction based on correlation and sentiment
        if correlation_type == 'direct':
            if sentiment == 'positive':
                direction = 'UP'
            elif sentiment == 'negative':
                direction = 'DOWN'
            else:
                direction = 'NEUTRAL'
                confidence *= 0.8
        
        elif correlation_type == 'positive':
            if sentiment == 'positive':
                direction = 'UP'
            elif sentiment == 'negative':
                direction = 'DOWN'
            else:
                direction = 'NEUTRAL'
                confidence *= 0.8
        
        elif correlation_type == 'negative':
            if sentiment == 'positive':
                direction = 'DOWN'
            elif sentiment == 'negative':
                direction = 'UP'
            else:
                direction = 'NEUTRAL'
                confidence *= 0.8
        
        else:  # variable
            direction = 'NEUTRAL'
            confidence *= 0.7
        
        # Enforce confidence bounds
        confidence = max(config.MIN_CONFIDENCE_ALLOWED, 
                        min(confidence, config.MAX_CONFIDENCE_ALLOWED))
        
        return direction, round(confidence, 1)
    
    def _determine_risk_level(self, confidence: float, impact_level: str) -> str:
        """Determine risk level"""
        # Lower confidence = higher risk
        if confidence < 50:
            return 'HIGH'
        elif confidence < 70:
            risk = 'MEDIUM' if impact_level != 'HIGH' else 'HIGH'
            return risk
        else:
            # Even high confidence has at least medium risk
            return 'MEDIUM' if impact_level == 'HIGH' else 'LOW'
    
    def _generate_reasoning(self, category: str, sentiment: str, asset: str, direction: str) -> str:
        """Generate human-readable reasoning"""
        reasons = []
        
        # Category context
        reasons.append(f"{category.replace('_', ' ').title()} development")
        
        # Sentiment
        if sentiment != 'neutral':
            reasons.append(f"{sentiment} market sentiment")
        
        # Asset-specific
        if category == 'interest_rates' and asset in ['Gold', 'Silver']:
            reasons.append('inverse rate relationship')
        elif category == 'geopolitics' and asset in ['Gold', 'Silver']:
            reasons.append('safe-haven demand')
        elif category == 'inflation' and asset in ['Gold', 'Silver']:
            reasons.append('inflation hedge appeal')
        
        return ', '.join(reasons[:3])
    
    def _generate_scenarios(self, asset: str, direction: str, category: str, sentiment: str) -> Tuple[str, str]:
        """Generate base and alternative scenarios"""
        category_name = category.replace('_', ' ')
        
        if direction == 'UP':
            base = f"{asset} likely to experience upward pressure from {category_name} developments with {sentiment} market reaction."
            alternative = f"If market sentiment shifts or counteracting factors emerge, {asset} may consolidate or face resistance at key levels."
        
        elif direction == 'DOWN':
            base = f"{asset} likely to face downward pressure from {category_name} developments with {sentiment} market reaction."
            alternative = f"However, support levels or risk-off flows could limit downside or trigger reversal."
        
        else:  # NEUTRAL
            base = f"{asset} likely to trade sideways as {category_name} news has mixed market implications."
            alternative = f"Breakout possible if additional catalysts emerge or market sentiment clarifies."
        
        return base, alternative


# Singleton
_forecaster = None

def get_forecaster() -> Forecaster:
    """Get forecaster instance"""
    global _forecaster
    if _forecaster is None:
        _forecaster = Forecaster()
    return _forecaster
