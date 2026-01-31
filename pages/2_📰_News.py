"""
News Page
Economic news feed with Arabic translation and filtering
AUTO-REFRESHING - Worker collects news automatically
"""

import streamlit as st
from datetime import datetime, timedelta
import json
import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db.db import get_db

st.set_page_config(page_title="Economic News", page_icon="📰", layout="wide")

# Auto-refresh every 30 seconds
if 'last_refresh_news' not in st.session_state:
    st.session_state.last_refresh_news = time.time()

current_time = time.time()
if current_time - st.session_state.last_refresh_news > 30:
    st.session_state.last_refresh_news = current_time
    st.rerun()

st.title("📰 Economic News Feed")
st.caption("🔄 Auto-refreshing every 30 seconds | Worker automatically collects & translates news")

# Sidebar filters
st.sidebar.subheader("🔍 Filters")


def normalize_affected(affected) -> list[str]:
    """Normalize affected_assets into a clean list of unique strings.

    Supported inputs:
    - None
    - empty string
    - comma-separated string
    - JSON list stored as text
    - actual list (already parsed)
    """
    if affected is None:
        return []

    if isinstance(affected, list):
        items = [str(x).strip() for x in affected if str(x).strip()]
    elif isinstance(affected, str):
        raw = affected.strip()
        if not raw:
            return []

        # Try JSON list
        if raw.startswith('[') and raw.endswith(']'):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    items = [str(x).strip() for x in parsed if str(x).strip()]
                else:
                    items = []
            except Exception:
                # Fall back to comma-separated
                items = [x.strip() for x in raw.split(',') if x.strip()]
        elif ',' in raw:
            items = [x.strip() for x in raw.split(',') if x.strip()]
        else:
            items = [raw]
    else:
        return []

    # De-dup while preserving order
    seen = set()
    out: list[str] = []
    for x in items:
        if x not in seen:
            out.append(x)
            seen.add(x)
    return out


def generate_professional_commentary(news_item, language="EN"):
    """Generate institutional-grade market commentary following professional analyst standards.
    
    Args:
        news_item: Dictionary containing news data
        language: "EN" for English (default) or "AR" for Arabic
    
    Returns:
        Formatted professional commentary string
    """
    
    category = (news_item.get('category') or 'general').replace('_', ' ').title()
    sentiment = str(news_item.get('sentiment') or 'neutral').lower()
    impact = str(news_item.get('impact_level') or 'low').upper()
    affected_assets = normalize_affected(news_item.get('affected_assets'))
    confidence = news_item.get('confidence', 0)
    
    commentary_parts = []
    
    # === 1) MARKET IMPACT ASSESSMENT ===
    commentary_parts.append("## 1. Market Impact Assessment\n")
    
    if impact == 'CRITICAL':
        commentary_parts.append("**Impact Level: Critical**\n\nThis development represents a significant market catalyst with immediate implications for asset pricing and risk positioning. The news warrants heightened attention from institutional portfolio managers and policy observers. Potential for increased volatility across correlated markets, with likely spillover effects beyond the directly affected assets. Institutional order flow and positioning adjustments may amplify initial market reactions.")
    elif impact == 'HIGH':
        commentary_parts.append("**Impact Level: High**\n\nThis release carries substantial weight in the current market environment. The information contributes meaningfully to the evolving macro narrative and may influence medium-term positioning decisions. Market participants should monitor follow-through in related assets and derivatives markets. Risk premia adjustments across asset classes may materialize over the coming sessions.")
    elif impact == 'MEDIUM':
        commentary_parts.append("**Impact Level: Moderate**\n\nThis development adds incremental information to the broader market picture without representing a decisive catalyst. The news fits within the established range of market expectations and is unlikely to trigger major portfolio reallocations. Nevertheless, it contributes to the accumulation of data points that shape medium-term sentiment and may influence tactical positioning at the margin.")
    else:
        commentary_parts.append("**Impact Level: Low**\n\nThis represents routine information flow with limited immediate market implications. While the data point adds context to the ongoing economic narrative, it is unlikely to drive material changes in risk appetite or asset allocation decisions. Market impact, if any, should remain confined to directly related instruments with minimal cross-asset spillover.")
    
    # === 2) MONETARY / MACRO CONTEXT ===
    if category in ['Interest Rates', 'Inflation', 'Employment', 'Gdp']:
        commentary_parts.append("\n## 2. Monetary & Macroeconomic Context\n")
        
        if category == 'Interest Rates':
            commentary_parts.append(f"Interest rate developments directly influence the discount mechanism for equity valuations, fixed-income returns, and currency carry dynamics. The {sentiment} tone of this news affects forward rate expectations and the shape of the yield curve. Central bank reaction function sensitivities remain elevated, particularly regarding terminal rate expectations and the pace of policy normalization. Duration exposure in fixed-income portfolios and growth-sensitive equity sectors face heightened sensitivity to rate path revisions. Cross-market correlations between rates, currencies, and equity risk premia deserve close monitoring.")
        
        elif category == 'Inflation':
            commentary_parts.append(f"Inflation trajectory remains the primary input variable for monetary policy globally. This {sentiment} inflation signal impacts real interest rate expectations, breakeven calculations, and the relative attractiveness of nominal versus inflation-protected securities. The news affects central banks' tolerance for maintaining accommodative policy and the potential timing of normalization measures. Commodity exposure, TIPS positioning, and inflation-sensitive equity sectors (materials, energy) warrant reassessment. Second-round effects through wage bargaining and inflation expectations anchoring remain key transmission mechanisms.")
        
        elif category == 'Employment':
            commentary_parts.append(f"Labor market data serves dual significance: as a real-time economic activity gauge and a forward indicator for wage pressures and consumption dynamics. The {sentiment} employment reading influences Fed/ECB reaction functions regarding the pace of policy normalization. Tight labor markets typically support consumer spending and service sector resilience but may complicate inflation management. The employment-inflation trade-off remains central to policy deliberations. Equity sectors with high labor intensity and consumer discretionary exposure show elevated sensitivity.")
        
        elif category == 'Gdp':
            commentary_parts.append(f"GDP data provides the foundational backdrop for corporate earnings growth expectations, credit quality assessments, and aggregate demand forecasts. This {sentiment} growth signal influences equity risk premium calculations and the sustainability of current valuations. Diverging growth trajectories across regions create relative value opportunities in both equity and currency markets. The growth-inflation mix affects optimal asset allocation between defensive and cyclical exposures. Central banks' dual mandates (growth and inflation) make GDP data critical for policy path expectations.")
    
    # === 3) ASSET-SPECIFIC IMPLICATIONS ===
    if affected_assets:
        commentary_parts.append("\n## 3. Asset-Specific Implications\n")
        
        for asset in affected_assets:
            if 'USD' in asset or 'Dollar' in asset:
                commentary_parts.append(f"\n**{asset} (U.S. Dollar Index)**\n\nThe dollar functions as the global reserve currency and primary funding vehicle for international transactions. Strength in the USD affects multinational corporate earnings through translation effects, emerging market debt servicing capacity, and commodity prices (which are dollar-denominated). Current drivers include Fed policy divergence versus other major central banks, real yield differentials, and safe-haven demand during risk-off episodes. DXY positioning by leveraged funds and central bank reserve management decisions provide insight into near-term direction. Dollar strength typically correlates negatively with commodity prices and EM assets while supporting U.S. import consumption.")
            
            elif 'Gold' in asset:
                commentary_parts.append(f"\n**{asset} (Gold)**\n\nGold serves as a non-yielding store of value with dual characteristics: an inflation hedge and a safe-haven asset during geopolitical or financial stress. The primary driver is real interest rates (nominal rates minus inflation expectations) - as real rates rise, gold's opportunity cost increases. Additional factors include dollar strength (negative correlation), central bank buying programs (especially from Asian and EM central banks), jewelry demand seasonality, and geopolitical risk premia. Gold responds to monetary policy uncertainty and financial market stress. Unlike other commodities, gold lacks industrial demand sensitivity, making it purely a monetary metal.")
            
            elif 'Silver' in asset:
                commentary_parts.append(f"\n**{asset} (Silver)**\n\nSilver exhibits hybrid characteristics: approximately 50% industrial demand (particularly from solar panel manufacturing, electronics, and EV components) and 50% monetary/jewelry demand. This creates higher volatility than gold with exposure to both industrial recession risk and monetary factors. The gold-silver ratio provides insight into relative value positioning. Silver benefits from green energy transition trends (solar panels consume significant silver) but suffers during manufacturing slowdowns. Lower market liquidity compared to gold creates amplified price swings. Silver's beta to gold remains elevated while maintaining industrial cyclicality.")
            
            elif 'Oil' in asset or 'Crude' in asset:
                commentary_parts.append(f"\n**{asset} (Crude Oil)**\n\nOil prices balance supply-side dynamics (OPEC+ production decisions, U.S. shale output, geopolitical supply disruptions) against demand expectations driven by global growth forecasts and mobility trends. Current market structure (contango vs backwardation) signals inventory conditions and forward demand expectations. Energy security considerations and geopolitical risk premia add volatility. Oil price movements cascade through inflation data (headline vs core inflation split), transportation costs, and input costs for manufacturing. Refining margins (crack spreads) and inventory levels (EIA weekly data) provide tactical signals. Currency effects remain significant as oil trades in dollars.")
            
            elif 'Bitcoin' in asset or 'BTC' in asset or 'Crypto' in asset:
                commentary_parts.append(f"\n**{asset} (Bitcoin/Crypto)**\n\nBitcoin increasingly trades as a risk-on asset with elevated correlation to technology equities and sensitivity to liquidity conditions. Regulatory developments (ETF approvals, custody rules, taxation) materially impact institutional adoption trajectories. The fixed supply schedule (halving events) creates supply-side dynamics distinct from traditional assets. On-chain metrics (exchange flows, active addresses, miner behavior) supplement traditional technical analysis. Correlation with broader risk assets has increased as institutional participation expands, reducing diversification benefits. Volatility remains structurally higher than traditional assets, requiring appropriate position sizing and risk management protocols.")
    
    # === 4) CONFIDENCE ASSESSMENT ===
    commentary_parts.append("\n## 4. Confidence Assessment\n")
    
    if confidence and confidence > 0:
        if confidence >= 75:
            commentary_parts.append(f"**Analytical Confidence: {confidence:.0f}%**\n\nHigh confidence is supported by reliable sourcing, clear economic transmission mechanisms, and established historical precedents. The signal-to-noise ratio is favorable, and the directional implications are relatively unambiguous. However, markets are forward-looking and may have partially discounted this information. Actual price action depends on positioning, liquidity conditions, and competing narratives. Confidence reflects data quality and analytical clarity but does not eliminate execution risk or unexpected market reactions.")
        elif confidence >= 50:
            commentary_parts.append(f"**Analytical Confidence: {confidence:.0f}%**\n\nModerate confidence reflects some uncertainty in either the sourcing reliability, the magnitude of market impact, or the timing of transmission effects. Multiple offsetting factors or competing narratives may dilute the directional signal. Market microstructure and positioning dynamics could amplify or dampen the expected response. Confirmation from related data points or market price action would strengthen the analytical thesis. Position sizing should account for this uncertainty, and stop-loss disciplines remain critical.")
        else:
            commentary_parts.append(f"**Analytical Confidence: {confidence:.0f}%**\n\nLower confidence indicates significant ambiguity in either the underlying data quality, the economic transmission mechanisms, or the market's likely interpretation. The situation may be evolving rapidly, or multiple cross-currents may obscure the net directional impact. This environment favors flexibility over conviction. Avoid outsized directional bets and maintain liquidity for tactical adjustments. Monitor subsequent data releases and market price action for confirmation or refutation of the initial hypothesis.")
    else:
        commentary_parts.append("**Analytical Confidence: Not Specified**\n\nInsufficient information to assign a numerical confidence level. Market participants should exercise elevated caution and await additional data points or clarification before establishing directional views. Prioritize risk management over return maximization in ambiguous informational environments.")
    
    # === 5) RISK & POSITIONING CONSIDERATIONS ===
    commentary_parts.append("\n## 5. Risk & Positioning Considerations\n")
    
    if sentiment == 'positive':
        commentary_parts.append("**Risk Bias: Constructive / Risk-On**\n\nThe positive tone supports risk-taking in affected assets, though market participants should remain vigilant for sentiment reversals or technical exhaustion signals. Consider incremental exposure additions rather than aggressive positioning, particularly if valuations have extended or momentum indicators show divergences. Monitor cross-asset confirmation (credit spreads, volatility indices, breadth indicators) to validate the risk-on thesis. Profit-taking disciplines remain important even in constructive environments. Liquidity conditions and positioning data (CFTC commitments, fund flows) provide insight into sustainability of moves. Defensive hedges may be scaled back but should not be eliminated entirely given macro uncertainties.")
    elif sentiment == 'negative':
        commentary_parts.append("**Risk Bias: Defensive / Risk-Off**\n\nThe negative tone suggests elevated focus on capital preservation and defensive positioning. Consider hedging strategies (options, inverse positions, safe-haven allocations) appropriate to portfolio mandates and risk tolerances. Volatility tends to rise during risk-off episodes, affecting option pricing and position sizing calculations. Watch for capitulation signals (VIX spikes, breadth deterioration, forced liquidations) that may present tactical entry points. Policy responses (central bank interventions, fiscal measures) often provide relief during sustained risk-off environments. Maintain adequate liquidity buffers to navigate temporary dislocations without forced selling.")
    else:
        commentary_parts.append("**Risk Bias: Neutral / Wait-and-See**\n\nThe neutral sentiment profile suggests no immediate directional catalyst. This environment favors range-bound trading strategies, volatility selling (if implied exceeds realized), and use of waiting capital to assess emerging opportunities. Reduce leverage and exposure to low-conviction positions. Focus on risk management, portfolio rebalancing, and preparation for the next clear directional catalyst. Neutral environments often precede inflection points, so maintain readiness for regime shifts. Monitor technical levels, sentiment indicators, and upcoming event risks for early signals of directional resolution.")
    
    # Professional Disclaimer
    commentary_parts.append("\n\n---\n\n*This analysis represents automated assessment based on available data and established analytical frameworks. Markets are forward-looking and may react counter-intuitively to news flow due to positioning, expectations, and competing narratives. This commentary is not financial advice, investment recommendations, or a solicitation to trade. Investors should conduct independent due diligence, consult qualified financial advisors, and carefully consider their own risk tolerance and investment objectives before making any investment decisions. Past performance is not indicative of future results.*")
    
    return "\n".join(commentary_parts)

asset_filter = st.sidebar.selectbox(
    "Filter by Asset",
    ["All", "USD Index", "Gold", "Silver", "Oil", "Bitcoin", "USD (legacy)"]
)

impact_filter = st.sidebar.selectbox(
    "Impact Level",
    ["All", "Critical", "High", "Medium", "Low"]
)

category_filter = st.sidebar.selectbox(
    "Category",
    ["All", "Interest Rates", "Inflation", "Employment", "Energy", "Geopolitics", "Crypto", "GDP"]
)

sentiment_filter = st.sidebar.selectbox(
    "Sentiment",
    ["All", "Positive", "Negative", "Neutral"]
)

# Main content
db = get_db()

# Get news from database
news_items = db.get_recent_news(limit=50, hours=168)  # default: last 7 days for a richer feed

total_before_filters = len(news_items)

# Apply filters
if asset_filter not in ["All"]:
    if asset_filter == "USD (legacy)":
        asset_filter_query = "USD"
    else:
        asset_filter_query = asset_filter

    filtered = []
    for n in news_items:
        affected_list = normalize_affected(n.get('affected_assets'))
        if asset_filter_query in affected_list:
            filtered.append(n)
        elif asset_filter_query == 'USD Index' and 'USD' in affected_list:
            filtered.append(n)
    news_items = filtered

if impact_filter != "All":
    # DB stores impact_level as LOW/MEDIUM/HIGH typically
    desired = impact_filter.strip().upper()
    news_items = [n for n in news_items if str(n.get('impact_level') or '').strip().upper() == desired]

if category_filter != "All":
    news_items = [n for n in news_items if (n.get('category') or 'general').replace('_', ' ').title() == category_filter]

if sentiment_filter != "All":
    desired = sentiment_filter.strip().lower()
    news_items = [n for n in news_items if str(n.get('sentiment') or '').strip().lower() == desired]

st.sidebar.caption(f"Total retrieved: {total_before_filters}")
st.sidebar.caption(f"After filters: {len(news_items)}")

# Display count
st.caption(
    f"Showing {len(news_items)} of {total_before_filters} news items | Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
)

if total_before_filters <= 1:
    st.info(
        "Only 1 news item is currently stored in the database. "
        "If you expected more, this is a data-availability/ingestion issue (worker/news sources), not a UI filtering bug."
    )

if not news_items:
    st.info("📭 No news items found matching filters. Worker is continuously collecting economic news...")
else:
    # Display news items
    for idx, news in enumerate(news_items):
        with st.container():
            col1, col2 = st.columns([3, 1])
            
            with col1:
                # Title (English)
                st.markdown(f"### {news.get('title_en', 'N/A')}")
                
                # Title (Arabic)
                if news.get('title_ar'):
                    st.markdown(f"<div style='direction: rtl; text-align: right; font-weight: bold;'>{news.get('title_ar')}</div>", unsafe_allow_html=True)
                
                # Content preview (English)
                content = news.get('body_en', '')
                if content:
                    preview = content[:300] + "..." if len(content) > 300 else content
                    st.write(preview)
                
                # Professional Commentary Section
                with st.expander("📊 **Professional Market Analysis & Commentary**", expanded=False):
                    commentary = generate_professional_commentary(news)
                    st.markdown(commentary)
                
                # Arabic content preview
                if news.get('body_ar'):
                    content_ar = news.get('body_ar', '')
                    preview_ar = content_ar[:200] + "..." if len(content_ar) > 200 else content_ar
                    st.markdown(f"<div style='direction: rtl; text-align: right; color: #CCC;'>{preview_ar}</div>", unsafe_allow_html=True)
                
                # Metadata
                source = news.get('source', 'Unknown')
                published = news.get('published_at', news.get('fetched_at', 'N/A'))
                if published != 'N/A':
                    try:
                        dt = datetime.fromisoformat(published.replace('Z', '+00:00'))
                        published = dt.strftime('%Y-%m-%d %H:%M')
                    except:
                        pass
                
                st.caption(f"📅 {published} | 📰 {source} | Reliability: {news.get('source_reliability', 0.8)*100:.0f}%")
                
                # Link
                if news.get('url'):
                    st.markdown(f"[Read full article →]({news['url']})")
            
            with col2:
                # Impact badge
                impact = news.get('impact_level', 'N/A')
                if impact in ['Critical', 'High']:
                    st.markdown(f"🔴 **{impact.upper()} IMPACT**")
                elif impact == 'Medium':
                    st.markdown("🟡 **MEDIUM IMPACT**")
                elif impact == 'Low':
                    st.markdown("🟢 **LOW IMPACT**")
                
                # Sentiment
                sentiment_raw = str(news.get('sentiment') or 'neutral').strip().lower()
                sentiment_label = sentiment_raw.title() if sentiment_raw else 'Neutral'
                if sentiment_raw == 'positive':
                    st.success(f"📈 {sentiment_label}")
                elif sentiment_raw == 'negative':
                    st.error(f"📉 {sentiment_label}")
                else:
                    st.info(f"➡️ {sentiment_label}")
                
                # Category
                category = news.get('category') or 'general'
                category = category.replace('_', ' ').title()
                st.info(f"🏷️ {category}")
                
                # Confidence
                confidence = news.get('confidence')
                if confidence is not None and confidence > 0:
                    st.metric("Confidence", f"{confidence:.0f}%")
                
                # Affected assets
                affected_raw = news.get('affected_assets')
                try:
                    affected_list = normalize_affected(affected_raw)
                    if affected_raw is not None and not affected_list:
                        st.warning("Malformed affected_assets; showing item anyway.")
                    if affected_list:
                        st.markdown("**Affected:**")
                        for asset in affected_list:
                            st.markdown(f"• {asset}")
                except Exception:
                    st.warning("Malformed affected_assets; showing item anyway.")
            
            st.markdown("---")
    
    # Pagination info
    if len(news_items) >= 100:
        st.info("Showing most recent 100 items. Older items are stored in the database.")

# Disclaimer
st.markdown("---")
st.markdown("""
<div style='background-color: #2E1A1A; border: 1px solid #D4AF37; border-radius: 5px; padding: 15px;'>
<strong>⚠️ Disclaimer</strong><br>
News analysis is automated and probabilistic using NLP. Always verify information from original sources. 
This platform does not constitute financial advice.
</div>
""", unsafe_allow_html=True)
