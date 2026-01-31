"""
NLP and Impact Analysis Engine
Analyzes news content and determines market impact
"""

import re
from typing import Dict, List, Tuple
import config

class ImpactEngine:
    """Analyzes news and determines impact on assets"""
    
    # News categories with keywords
    CATEGORIES = {
        'interest_rates': ['interest rate', 'fed', 'federal reserve', 'ecb', 'central bank', 
                          'monetary policy', 'rate hike', 'rate cut', 'fomc', 'policy rate'],
        'inflation': ['inflation', 'cpi', 'pce', 'consumer price', 'producer price', 'ppi',
                     'price index', 'deflation', 'disinflation'],
        'employment': ['employment', 'unemployment', 'jobs', 'nonfarm', 'payroll', 
                      'jobless claims', 'labor market', 'workforce'],
        'gdp': ['gdp', 'gross domestic', 'economic growth', 'recession', 'expansion',
               'contraction', 'output'],
        'energy': ['oil', 'crude', 'opec', 'energy', 'petroleum', 'wti', 'brent',
                  'natural gas', 'refinery'],
        'geopolitics': ['war', 'conflict', 'sanctions', 'trade war', 'military', 'geopolitical',
                       'tension', 'dispute', 'crisis'],
        'crypto': ['bitcoin', 'cryptocurrency', 'crypto', 'ethereum', 'blockchain', 
                  'sec crypto', 'digital currency']
    }
    
    # Asset correlations with news categories
    CORRELATIONS = {
        'interest_rates': {
            'USD Index': ('positive', 0.7),
            'Gold': ('negative', 0.8),
            'Silver': ('negative', 0.7),
            'Bitcoin': ('negative', 0.6)
        },
        'inflation': {
            'USD Index': ('negative', 0.6),
            'Gold': ('positive', 0.9),
            'Silver': ('positive', 0.8),
            'Oil': ('positive', 0.5)
        },
        'employment': {
            'USD Index': ('positive', 0.6),
            'Gold': ('negative', 0.5)
        },
        'energy': {
            'Oil': ('direct', 1.0),
            'USD Index': ('negative', 0.4),
            'Gold': ('positive', 0.3)
        },
        'crypto': {
            'Bitcoin': ('direct', 1.0)
        },
        'geopolitics': {
            'Gold': ('positive', 0.8),
            'Silver': ('positive', 0.6),
            'USD Index': ('positive', 0.5),
            'Oil': ('variable', 0.5),
            'Bitcoin': ('negative', 0.4)
        }
    }
    
    def analyze_news(self, news_item: Dict) -> Dict:
        """
        Analyze news and return impact analysis
        Returns: {category, sentiment, impact_level, confidence, affected_assets}
        """
        title = news_item.get('title_en', '')
        body = news_item.get('body_en', '')
        text = (title + " " + body).lower()
        
        # Detect category
        category = self._detect_category(text)
        
        # Detect sentiment
        sentiment = self._detect_sentiment(text)
        
        # Determine affected assets
        affected_assets = self._determine_affected_assets(category, text)
        
        # Calculate impact level
        impact_level = self._calculate_impact_level(text, category, sentiment)
        
        # Calculate confidence
        confidence = self._calculate_confidence(
            news_item, text, category, impact_level
        )
        
        return {
            'category': category,
            'sentiment': sentiment,
            'impact_level': impact_level,
            'confidence': confidence,
            'affected_assets': affected_assets
        }
    
    def _detect_category(self, text: str) -> str:
        """Detect news category"""
        scores = {}
        
        for category, keywords in self.CATEGORIES.items():
            score = sum(1 for keyword in keywords if keyword in text)
            if score > 0:
                scores[category] = score
        
        if not scores:
            return 'general'
        
        return max(scores, key=scores.get)
    
    def _detect_sentiment(self, text: str) -> str:
        """Detect sentiment direction (positive/negative/neutral)"""
        # Note: sentiment here is a coarse directional signal for market reaction,
        # not "good/bad" morality. It is intentionally simple and domain-biased.
        positive_words = [
            'increase', 'rise', 'surge', 'gain', 'strong', 'growth', 'better', 
            'improve', 'beat', 'exceed', 'boost', 'jump', 'rally', 'advance',
            'higher', 'up', 'recovery', 'expansion'
        ]
        
        negative_words = [
            'decrease', 'fall', 'drop', 'decline', 'weak', 'recession', 'miss', 
            'worse', 'concern', 'fear', 'crisis', 'crash', 'plunge', 'slump',
            'lower', 'down', 'contraction', 'slowdown'
        ]

        # Macro/market-specific cues
        positive_words += [
            'rate cut', 'cuts rates', 'dovish', 'easing', 'stimulus', 'liquidity',
            'cooling inflation', 'disinflation', 'soft landing', 'pause hikes',
        ]
        negative_words += [
            'rate hike', 'hikes rates', 'hawkish', 'tightening', 'inflation hot',
            'sticky inflation', 'higher for longer', 'default', 'downgrade',
        ]

        # Keep single-word variants last so phrase matches still count
        positive_words += ['cut', 'easing', 'dovish']
        negative_words += ['hike', 'tightening', 'hawkish']
        
        positive_score = sum(1 for word in positive_words if word in text)
        negative_score = sum(1 for word in negative_words if word in text)
        
        if positive_score > negative_score + 1:
            return 'positive'
        elif negative_score > positive_score + 1:
            return 'negative'
        else:
            return 'neutral'
    
    def _determine_affected_assets(self, category: str, text: str) -> List[str]:
        """Determine which assets are affected"""
        affected = set()
        
        # Direct mentions
        if 'gold' in text:
            affected.add('Gold')
        if 'silver' in text:
            affected.add('Silver')
        if any(word in text for word in ['dollar', 'usd', 'dxy']):
            affected.add('USD Index')
        if any(word in text for word in ['oil', 'crude', 'wti', 'brent']):
            affected.add('Oil')
        if any(word in text for word in ['bitcoin', 'btc', 'crypto']):
            affected.add('Bitcoin')
        
        # Based on category correlation
        if category in self.CORRELATIONS:
            for asset in self.CORRELATIONS[category].keys():
                affected.add(asset)
        
        # If no specific assets, assume broad impact
        if not affected:
            affected = {'USD Index', 'Gold', 'Oil'}
        
        return list(affected)
    
    def _calculate_impact_level(self, text: str, category: str, sentiment: str) -> str:
        """Calculate impact level (HIGH/MEDIUM/LOW)"""
        # High impact indicators
        high_impact_words = [
            'surge', 'plunge', 'soar', 'crash', 'significant', 'major', 'sharp',
            'dramatic', 'emergency', 'crisis', 'shock', 'surprise', 'unexpected'
        ]
        
        # Check for strong words
        strong_count = sum(1 for word in high_impact_words if word in text)
        
        # Check for numerical data (often means concrete news)
        has_numbers = bool(re.search(r'\d+\.?\d*%', text)) or bool(re.search(r'\$\d+', text))
        
        # Determine impact
        if strong_count >= 2 or 'emergency' in text or 'crisis' in text:
            return 'HIGH'

        # Macro categories are often market-moving even without dramatic adjectives.
        # If we detected a macro category, allow MEDIUM on actionable cues.
        macro_categories = {'interest_rates', 'inflation', 'employment', 'gdp'}
        if category in macro_categories:
            actionable_cues = any(
                cue in text
                for cue in (
                    'rate hike', 'rate cut', 'fomc', 'fed', 'cpi', 'pce',
                    'payroll', 'nonfarm', 'jobless claims', 'unemployment',
                    'recession', 'gdp', 'growth'
                )
            )
            if strong_count >= 1 or has_numbers or (actionable_cues and sentiment != 'neutral'):
                return 'MEDIUM'

        if strong_count >= 1 or (has_numbers and sentiment != 'neutral'):
            return 'MEDIUM'

        return 'LOW'
    
    def _calculate_confidence(self, news_item: Dict, text: str, category: str, impact_level: str) -> float:
        """
        Calculate confidence score (0-100)
        Data quality > AI - reduce confidence for weak data
        """
        base_confidence = 50.0
        
        # Source reliability
        source_reliability = news_item.get('source_reliability', 0.8)
        base_confidence += (source_reliability - 0.5) * 20
        
        # Content quality
        body_length = len(news_item.get('body_en', ''))
        if body_length < config.MIN_NEWS_CONTENT_LENGTH:
            base_confidence -= config.WEAK_SOURCE_PENALTY
        elif body_length > 200:
            base_confidence += 10
        
        # Category clarity
        if category != 'general':
            base_confidence += 10
        
        # Specific numbers/data
        if re.search(r'\d+\.?\d*%', text) or re.search(r'\$\d+', text):
            base_confidence += 10
        
        # Impact level adjustment
        if impact_level == 'HIGH':
            base_confidence += config.HIGH_IMPACT_CONFIDENCE_BOOST
        elif impact_level == 'LOW':
            base_confidence -= config.LOW_IMPACT_CONFIDENCE_PENALTY
        
        # Surprise factor
        if 'surprise' in text or 'unexpected' in text:
            base_confidence += 5
        
        # Ambiguity penalty
        ambiguous_words = ['may', 'might', 'could', 'possibly', 'unclear', 'uncertain']
        ambiguity_count = sum(1 for word in ambiguous_words if word in text)
        if ambiguity_count >= 2:
            base_confidence -= config.AMBIGUOUS_NEWS_PENALTY
        
        # Enforce bounds
        confidence = max(config.MIN_CONFIDENCE_ALLOWED, min(base_confidence, config.MAX_CONFIDENCE_ALLOWED))
        
        return round(confidence, 1)


# Singleton
_impact_engine = None

def get_impact_engine() -> ImpactEngine:
    """Get impact engine instance"""
    global _impact_engine
    if _impact_engine is None:
        _impact_engine = ImpactEngine()
    return _impact_engine
