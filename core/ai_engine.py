"""
AI Analysis Engine for Dahab AI
Handles news classification, impact analysis, and probabilistic forecasting
"""

import re
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

@dataclass
class NewsAnalysis:
    """News analysis result"""
    news_type: str
    affected_assets: List[str]
    impact_nature: str  # Positive, Negative, Neutral
    impact_strength: str  # High, Medium, Low
    confidence: float
    key_factors: List[str]

@dataclass
class MarketForecast:
    """Market forecast result"""
    asset: str
    expected_direction: str  # Up, Down, Neutral
    confidence_level: float  # 0-100
    time_horizon_minutes: int
    risk_level: str  # Low, Medium, High
    key_reasons: str
    base_scenario: str
    alternative_scenario: str

class AIAnalysisEngine:
    """Core AI engine for market analysis"""
    
    # Economic news types
    NEWS_TYPES = {
        'interest_rates': ['interest rate', 'fed', 'federal reserve', 'ecb', 'central bank', 'monetary policy', 'rate hike', 'rate cut'],
        'inflation': ['inflation', 'cpi', 'pce', 'consumer price', 'producer price', 'ppi'],
        'employment': ['employment', 'unemployment', 'jobs', 'nonfarm', 'payroll', 'jobless claims'],
        'gdp': ['gdp', 'gross domestic', 'economic growth', 'recession'],
        'energy': ['oil', 'crude', 'opec', 'energy', 'petroleum'],
        'geopolitics': ['war', 'conflict', 'sanctions', 'trade war', 'military', 'geopolitical'],
        'crypto': ['bitcoin', 'cryptocurrency', 'crypto', 'ethereum', 'blockchain', 'sec crypto']
    }
    
    # Asset correlation rules
    ASSET_CORRELATIONS = {
        'interest_rates': {
            'USD': 'positive',  # Higher rates strengthen USD
            'Gold': 'negative',  # Higher rates weaken gold
            'Silver': 'negative',
            'Bitcoin': 'negative'
        },
        'inflation': {
            'USD': 'negative',  # Higher inflation weakens USD
            'Gold': 'positive',  # Gold is inflation hedge
            'Silver': 'positive',
            'Oil': 'positive'
        },
        'employment': {
            'USD': 'positive',  # Strong jobs strengthen USD
            'Gold': 'negative'
        },
        'energy': {
            'Oil': 'direct',
            'USD': 'negative',  # Higher oil often weakens USD
            'Gold': 'positive'
        },
        'crypto': {
            'Bitcoin': 'direct'
        },
        'geopolitics': {
            'Gold': 'positive',  # Safe haven
            'Silver': 'positive',
            'USD': 'positive',  # Safe haven
            'Oil': 'variable',
            'Bitcoin': 'negative'  # Risk-off
        }
    }
    
    def __init__(self):
        pass
    
    def classify_news(self, title: str, content: str) -> NewsAnalysis:
        """
        Classify news and determine impact
        
        Returns NewsAnalysis with type, affected assets, and impact
        """
        text = (title + " " + content).lower()
        
        # Determine news type
        news_type = self._detect_news_type(text)
        
        # Determine affected assets
        affected_assets = self._determine_affected_assets(news_type, text)
        
        # Determine impact nature and strength
        impact_nature, impact_strength, key_factors = self._analyze_impact(text, news_type)
        
        # Calculate confidence based on clarity of news
        confidence = self._calculate_classification_confidence(text, news_type, key_factors)
        
        return NewsAnalysis(
            news_type=news_type,
            affected_assets=affected_assets,
            impact_nature=impact_nature,
            impact_strength=impact_strength,
            confidence=confidence,
            key_factors=key_factors
        )
    
    def _detect_news_type(self, text: str) -> str:
        """Detect the type of economic news"""
        scores = {}
        
        for news_type, keywords in self.NEWS_TYPES.items():
            score = sum(1 for keyword in keywords if keyword in text)
            if score > 0:
                scores[news_type] = score
        
        if not scores:
            return 'general'
        
        return max(scores, key=scores.get)
    
    def _determine_affected_assets(self, news_type: str, text: str) -> List[str]:
        """Determine which assets are affected"""
        affected = []
        
        # Direct mentions
        if 'gold' in text:
            affected.append('Gold')
        if 'silver' in text:
            affected.append('Silver')
        if 'dollar' in text or 'usd' in text or 'dxy' in text:
            affected.append('USD')
        if 'oil' in text or 'crude' in text or 'wti' in text or 'brent' in text:
            affected.append('Oil')
        if 'bitcoin' in text or 'btc' in text or 'crypto' in text:
            affected.append('Bitcoin')
        
        # Based on news type correlation
        if news_type in self.ASSET_CORRELATIONS:
            for asset in self.ASSET_CORRELATIONS[news_type].keys():
                if asset not in affected:
                    affected.append(asset)
        
        # If no specific assets, assume broad impact
        if not affected:
            affected = ['USD', 'Gold', 'Oil']
        
        return affected
    
    def _analyze_impact(self, text: str, news_type: str) -> Tuple[str, str, List[str]]:
        """Analyze impact nature and strength"""
        
        # Positive indicators
        positive_words = ['increase', 'rise', 'surge', 'gain', 'strong', 'growth', 'better', 'improve', 'beat', 'exceed']
        negative_words = ['decrease', 'fall', 'drop', 'decline', 'weak', 'recession', 'miss', 'worse', 'concern', 'fear']
        
        # Strength indicators
        strong_words = ['surge', 'plunge', 'soar', 'crash', 'significant', 'major', 'sharp', 'dramatic']
        
        positive_score = sum(1 for word in positive_words if word in text)
        negative_score = sum(1 for word in negative_words if word in text)
        strong_score = sum(1 for word in strong_words if word in text)
        
        # Determine nature
        if positive_score > negative_score:
            impact_nature = 'Positive'
        elif negative_score > positive_score:
            impact_nature = 'Negative'
        else:
            impact_nature = 'Neutral'
        
        # Determine strength
        if strong_score >= 2 or 'emergency' in text or 'crisis' in text:
            impact_strength = 'High'
        elif strong_score >= 1 or positive_score + negative_score >= 3:
            impact_strength = 'Medium'
        else:
            impact_strength = 'Low'
        
        # Extract key factors
        key_factors = []
        if news_type == 'interest_rates':
            if 'hike' in text or 'increase' in text:
                key_factors.append('Rate increase expected')
            elif 'cut' in text or 'lower' in text:
                key_factors.append('Rate decrease expected')
        
        if news_type == 'inflation':
            if any(word in text for word in ['high', 'rise', 'surge']):
                key_factors.append('Rising inflation')
            elif any(word in text for word in ['fall', 'decline', 'ease']):
                key_factors.append('Easing inflation')
        
        if 'surprise' in text or 'unexpected' in text:
            key_factors.append('Unexpected data')
            impact_strength = 'High'  # Surprises have higher impact
        
        if not key_factors:
            key_factors.append(f'{news_type.replace("_", " ").title()} related')
        
        return impact_nature, impact_strength, key_factors
    
    def _calculate_classification_confidence(self, text: str, news_type: str, key_factors: List[str]) -> float:
        """Calculate confidence in classification"""
        base_confidence = 0.5
        
        # More keywords matched = higher confidence
        if news_type in self.NEWS_TYPES:
            matches = sum(1 for keyword in self.NEWS_TYPES[news_type] if keyword in text)
            base_confidence += min(matches * 0.1, 0.3)
        
        # More key factors = higher confidence
        base_confidence += min(len(key_factors) * 0.05, 0.15)
        
        # Specific numbers/data = higher confidence
        if re.search(r'\d+\.?\d*%', text) or re.search(r'\$\d+', text):
            base_confidence += 0.1
        
        return min(base_confidence, 0.95)
    
    def generate_forecast(self, news_analysis: NewsAnalysis, asset: str, 
                         current_price: Optional[float] = None) -> MarketForecast:
        """
        Generate probabilistic forecast for an asset based on news analysis
        
        CRITICAL: All forecasts are probabilistic, never certain
        """
        
        # Determine expected direction based on correlations
        direction, confidence = self._determine_direction(news_analysis, asset)
        
        # Adjust confidence based on impact strength
        confidence = self._adjust_confidence(confidence, news_analysis)
        
        # Determine time horizon based on news type
        time_horizon = self._determine_time_horizon(news_analysis.news_type, news_analysis.impact_strength)
        
        # Determine risk level
        risk_level = self._determine_risk_level(news_analysis, confidence)
        
        # Generate reasoning
        key_reasons = self._generate_reasoning(news_analysis, asset, direction)
        
        # Generate scenarios
        base_scenario, alternative_scenario = self._generate_scenarios(
            asset, direction, news_analysis
        )
        
        return MarketForecast(
            asset=asset,
            expected_direction=direction,
            confidence_level=confidence,
            time_horizon_minutes=time_horizon,
            risk_level=risk_level,
            key_reasons=key_reasons,
            base_scenario=base_scenario,
            alternative_scenario=alternative_scenario
        )
    
    def _determine_direction(self, news_analysis: NewsAnalysis, asset: str) -> Tuple[str, float]:
        """Determine expected price direction and base confidence"""
        
        news_type = news_analysis.news_type
        impact_nature = news_analysis.impact_nature
        
        # Get correlation
        correlation = None
        if news_type in self.ASSET_CORRELATIONS:
            correlation = self.ASSET_CORRELATIONS[news_type].get(asset)
        
        if not correlation:
            return 'Neutral', 40.0
        
        # Determine direction based on correlation and impact
        if correlation == 'direct':
            if impact_nature == 'Positive':
                return 'Up', 65.0
            elif impact_nature == 'Negative':
                return 'Down', 65.0
            else:
                return 'Neutral', 45.0
        
        elif correlation == 'positive':
            if impact_nature == 'Positive':
                return 'Up', 60.0
            elif impact_nature == 'Negative':
                return 'Down', 60.0
            else:
                return 'Neutral', 45.0
        
        elif correlation == 'negative':
            if impact_nature == 'Positive':
                return 'Down', 60.0
            elif impact_nature == 'Negative':
                return 'Up', 60.0
            else:
                return 'Neutral', 45.0
        
        else:  # variable
            return 'Neutral', 40.0
    
    def _adjust_confidence(self, base_confidence: float, news_analysis: NewsAnalysis) -> float:
        """Adjust confidence based on news quality and strength"""
        
        confidence = base_confidence
        
        # Impact strength adjustment
        if news_analysis.impact_strength == 'High':
            confidence += 10
        elif news_analysis.impact_strength == 'Low':
            confidence -= 10
        
        # Classification confidence adjustment
        confidence = confidence * news_analysis.confidence
        
        # CRITICAL: Never exceed 85% confidence (following Dahab AI principles)
        confidence = min(confidence, 85.0)
        
        # CRITICAL: Never go below 25% confidence
        confidence = max(confidence, 25.0)
        
        return round(confidence, 1)
    
    def _determine_time_horizon(self, news_type: str, impact_strength: str) -> int:
        """Determine forecast time horizon in minutes"""
        
        # High impact = shorter term reaction
        if impact_strength == 'High':
            return 60  # 1 hour
        elif impact_strength == 'Medium':
            return 240  # 4 hours
        else:
            return 1440  # 1 day
    
    def _determine_risk_level(self, news_analysis: NewsAnalysis, confidence: float) -> str:
        """Determine risk level"""
        
        # Lower confidence = higher risk
        if confidence < 50:
            return 'High'
        elif confidence < 70:
            return 'Medium'
        else:
            # Even high confidence has at least medium risk
            return 'Medium' if news_analysis.impact_strength == 'High' else 'Low'
    
    def _generate_reasoning(self, news_analysis: NewsAnalysis, asset: str, direction: str) -> str:
        """Generate human-readable reasoning"""
        
        reasons = []
        
        # News type context
        reasons.append(f"{news_analysis.news_type.replace('_', ' ').title()} development")
        
        # Impact nature
        if news_analysis.impact_nature != 'Neutral':
            reasons.append(f"{news_analysis.impact_nature.lower()} sentiment")
        
        # Key factors
        if news_analysis.key_factors:
            reasons.append(news_analysis.key_factors[0].lower())
        
        # Asset-specific
        news_type = news_analysis.news_type
        if news_type == 'interest_rates' and asset in ['Gold', 'Silver']:
            reasons.append('inverse rate relationship')
        elif news_type == 'geopolitics' and asset in ['Gold', 'Silver']:
            reasons.append('safe-haven demand')
        
        return ', '.join(reasons[:3])  # Top 3 reasons
    
    def _generate_scenarios(self, asset: str, direction: str, news_analysis: NewsAnalysis) -> Tuple[str, str]:
        """Generate base and alternative scenarios"""
        
        news_type = news_analysis.news_type.replace('_', ' ')
        
        if direction == 'Up':
            base = f"{asset} rises as market responds to {news_type} developments with {news_analysis.impact_nature.lower()} sentiment."
            alternative = f"If market sentiment shifts or other factors intervene, {asset} may consolidate or face resistance."
        
        elif direction == 'Down':
            base = f"{asset} faces downward pressure from {news_type} developments with {news_analysis.impact_nature.lower()} market reaction."
            alternative = f"However, support levels or counteracting factors could limit downside or trigger reversal."
        
        else:  # Neutral
            base = f"{asset} likely to trade sideways as {news_type} news has mixed implications."
            alternative = f"Breakout possible if additional catalysts emerge or market sentiment clarifies."
        
        return base, alternative
    
    def evaluate_forecast(self, forecast: Dict, actual_price: float) -> Dict:
        """
        Evaluate forecast accuracy against actual outcome
        
        Returns evaluation metrics
        """
        forecast_price = forecast.get('price_at_forecast')
        expected_direction = forecast.get('expected_direction')
        confidence_level = forecast.get('confidence_level')
        
        if not forecast_price or not actual_price:
            return {
                'is_accurate': None,
                'actual_direction': 'Unknown',
                'price_change_percent': 0
            }
        
        # Calculate actual direction
        price_change_percent = ((actual_price - forecast_price) / forecast_price) * 100
        
        if price_change_percent > 0.1:  # More than 0.1% up
            actual_direction = 'Up'
        elif price_change_percent < -0.1:  # More than 0.1% down
            actual_direction = 'Down'
        else:
            actual_direction = 'Neutral'
        
        # Determine accuracy
        is_accurate = (expected_direction == actual_direction) or (expected_direction == 'Neutral' and abs(price_change_percent) < 0.5)
        
        return {
            'is_accurate': is_accurate,
            'actual_direction': actual_direction,
            'price_change_percent': round(price_change_percent, 2)
        }

# Singleton instance
_engine_instance = None

def get_engine() -> AIAnalysisEngine:
    """Get AI engine instance"""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = AIAnalysisEngine()
    return _engine_instance
