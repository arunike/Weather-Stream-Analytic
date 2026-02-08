import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import random
from faker import Faker
import json
import os
from pathlib import Path

from aml_rules import AMLRuleEngine
from credit_risk import CreditRiskEngine
from insurance_fraud import InsuranceFraudEngine
from market_manipulation import MarketManipulationEngine
from database import DatabaseManager, init_db

fake = Faker()

# Initialize database
try:
    init_db()
    db_manager = DatabaseManager()
except Exception as e:
    st.error(f"Database connection failed: {e}")
    st.stop()

# Page configuration
st.set_page_config(
    page_title="Financial Detection Platform",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        text-align: center;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        padding: 1rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        margin: 0.5rem 0;
    }
    .alert-critical {
        background-color: #ff4444;
        padding: 1rem;
        border-radius: 5px;
        color: white;
        margin: 0.5rem 0;
    }
    .alert-high {
        background-color: #ff8800;
        padding: 1rem;
        border-radius: 5px;
        color: white;
        margin: 0.5rem 0;
    }
    .alert-medium {
        background-color: #ffbb33;
        padding: 1rem;
        border-radius: 5px;
        color: white;
        margin: 0.5rem 0;
    }
    .alert-low {
        background-color: #00C851;
        padding: 1rem;
        border-radius: 5px;
        color: white;
        margin: 0.5rem 0;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 2rem;
    }
    .stTabs [data-baseweb="tab"] {
        height: 4rem;
        padding: 0 2rem;
        font-size: 1.1rem;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state with database data
if 'data_loaded' not in st.session_state:
    st.session_state.data_loaded = False
    try:
        st.session_state.aml_history = db_manager.get_aml_history()
        st.session_state.credit_results_history = db_manager.get_credit_history()
        st.session_state.insurance_history = db_manager.get_insurance_history()
        st.session_state.market_history = db_manager.get_market_history()
    except Exception as e:
        st.warning(f"Failed to load history from database: {e}")
        st.session_state.aml_history = []
        st.session_state.credit_results_history = []
        st.session_state.insurance_history = []
        st.session_state.market_history = []
    st.session_state.data_loaded = True

if 'aml_history' not in st.session_state:
    st.session_state.aml_history = []
if 'credit_results_history' not in st.session_state:
    st.session_state.credit_results_history = []
if 'insurance_history' not in st.session_state:
    st.session_state.insurance_history = []
if 'market_history' not in st.session_state:
    st.session_state.market_history = []

# Initialize engines
@st.cache_resource
def get_engines():
    return {
        'aml': AMLRuleEngine(),
        'credit': CreditRiskEngine(),
        'insurance': InsuranceFraudEngine(),
        'market': MarketManipulationEngine()
    }

engines = get_engines()

# Header
st.markdown('<h1 class="main-header">🏦 Unified Financial Detection Platform</h1>', unsafe_allow_html=True)
st.markdown("---")

# Sidebar - Platform Stats
with st.sidebar:
    st.header("📊 Platform Statistics")
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("AML Detection", len(st.session_state.aml_history))
        st.metric("Credit Scoring", len(st.session_state.credit_results_history))
    with col2:
        st.metric("Insurance Detection", len(st.session_state.insurance_history))
        st.metric("Market Monitoring", len(st.session_state.market_history))
    
    st.markdown("---")
    st.header("⚙️ System Settings")
    
    auto_generate = st.checkbox("Auto-generate test data", value=False)
    show_raw_data = st.checkbox("Show raw data", value=False)
    
    st.markdown("---")
    if st.button("🗑️ Clear All History", type="primary"):
        st.session_state.aml_history = []
        st.session_state.credit_results_history = []
        st.session_state.insurance_history = []
        st.session_state.market_history = []
        try:
            db_manager.clear_all_history()  # Clear database
            st.success("History cleared!")
        except Exception as e:
            st.error(f"Failed to clear history: {e}")
        st.rerun()

# Main content - Tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "💰 AML Detection",
    "📊 Credit Risk Scoring",
    "🛡️ Insurance Fraud Detection",
    "📈 Market Manipulation Detection"
])

with tab1:
    st.header("💰 AML Detection (Anti-Money Laundering)")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📝 Transaction Information")
        
        # Generate sample data button
        if st.button("🎲 Generate Test Transaction", key="gen_aml"):
            # Generate suspicious transaction
            suspicious = random.random() > 0.5
            
            if suspicious:
                # Structuring pattern
                amounts = [random.uniform(5000, 9500) for _ in range(random.randint(3, 7))]
                st.session_state.aml_amounts = amounts
                st.session_state.aml_sender = fake.name()
                st.session_state.aml_receiver = fake.name()
                st.session_state.aml_countries = ["Cayman Islands", "UAE", "Switzerland"]
            else:
                # Normal transaction
                st.session_state.aml_amounts = [random.uniform(500, 5000)]
                st.session_state.aml_sender = fake.name()
                st.session_state.aml_receiver = fake.name()
                st.session_state.aml_countries = ["USA", "UK", "China"]
        
        # Input fields
        transaction_id = st.text_input("Transaction ID", value=f"TXN-{random.randint(100000, 999999)}")
        sender = st.text_input("Sender", value=st.session_state.get('aml_sender', fake.name()))
        receiver = st.text_input("Receiver", value=st.session_state.get('aml_receiver', fake.name()))
        
        # Multiple amounts
        num_transactions = st.slider("Number of Transactions", 1, 10, 
                                     len(st.session_state.get('aml_amounts', [10000])))
        amounts = []
        cols = st.columns(min(num_transactions, 3))
        for i in range(num_transactions):
            with cols[i % 3]:
                default_amt = st.session_state.get('aml_amounts', [10000])[i] if i < len(st.session_state.get('aml_amounts', [])) else 10000
                amt = st.number_input(f"Amount #{i+1} (USD)", 
                                     value=float(default_amt),
                                     min_value=0.0,
                                     key=f"aml_amt_{i}")
                amounts.append(amt)
        
        # Countries
        all_countries = ["USA", "China", "UK", "Canada", "Switzerland", "Cayman Islands", 
                        "UAE", "Panama", "Russia", "North Korea", "Iran"]
        countries = st.multiselect("Countries Involved", all_countries,
                                  default=st.session_state.get('aml_countries', ["USA"]))
        
        # Detect button
        if st.button("🔍 Run AML Detection", type="primary", key="detect_aml"):
            # Create transactions as dictionaries
            transactions = []
            for i, amount in enumerate(amounts):
                tx = {
                    'transaction_id': f"{transaction_id}-{i}",
                    'sender_id': sender,
                    'receiver_id': receiver,
                    'amount': amount,
                    'timestamp': datetime.now() - timedelta(hours=i),
                    'currency': "USD",
                    'source_country': countries[0] if countries else "USA",
                    'destination_country': countries[-1] if len(countries) > 1 else countries[0],
                    'transaction_type': "wire_transfer"
                }
                transactions.append(tx)
            
            # Run detection
            all_alerts = []
            for tx in transactions:
                tx_alerts = engines['aml'].evaluate_transaction(tx, {})
                all_alerts.extend(tx_alerts)
            alerts = all_alerts
            
            # Store in history
            result = {
                'timestamp': datetime.now(),
                'transaction_id': transaction_id,
                'alerts': alerts,
                'num_transactions': len(transactions),
                'total_amount': sum(amounts)
            }
            st.session_state.aml_history.append(result)
            try:
                db_manager.save_aml_detection(result)  # Save to database
            except Exception as e:
                st.warning(f"Failed to save to database: {e}")
            
            # Display results
            st.success(f"✅ Detection completed! Found {len(alerts)} alert(s)")
            st.rerun()  # Refresh to update statistics
    
    with col2:
        st.subheader("📋 Detection Rules")
        st.info("""
        **Active Rules:**
        
        1️⃣ **Structuring Detection**
        - Detect ,000 reporting threshold avoidance
        - Analyze 24-hour transaction patterns
        
        2️⃣ **Rapid Movement**
        - Track fund flow chains
        - Identify money laundering networks
        
        3️⃣ **High-Risk Jurisdictions**
        - FATF blacklisted countries
        - Tax haven monitoring
        
        4️⃣ **Unusual Pattern Detection**
        - Historical behavior analysis
        - Statistical anomaly identification
        """)
    
    # Only display results section if there's history
    if not st.session_state.aml_history:
        st.info("""
        👋 **Welcome to AML Detection!**
        
        To get started:
        1. Click "🎲 Generate Test Transaction" to create sample data
        2. Or manually enter transaction details
        3. Click "🔍 Run AML Detection" to analyze
        """)
    
    # Display latest result
    if st.session_state.aml_history:
        st.markdown("---")
        st.subheader("🚨 Latest Detection Results")
        
        latest = st.session_state.aml_history[-1]
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Transactions", latest['num_transactions'])
        with col2:
            st.metric("Total Amount", f"${latest['total_amount']:,.2f}")
        with col3:
            st.metric("Alerts", len(latest['alerts']))
        with col4:
            risk_level = "High Risk" if latest['alerts'] else "Normal"
            st.metric("Risk Level", risk_level)
        
        # Display alerts
        if latest['alerts']:
            for alert in latest['alerts']:
                risk_class = f"alert-{alert.risk_level.lower()}"
                st.markdown(f"""
                <div class="{risk_class}">
                    <strong>🚨 {alert.rule_name}</strong><br>
                    Risk Level: {alert.risk_level} | Confidence: {alert.confidence*100:.1f}%<br>
                    Reason: {alert.reason}<br>
                    <small>Transaction ID: {alert.transaction_id}</small>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.success("✅ No suspicious activity detected")
        
        # History chart
        if len(st.session_state.aml_history) > 1:
            st.markdown("---")
            st.subheader("📊 Historical Trends")
            
            history_df = {
                'Time': [r['timestamp'] for r in st.session_state.aml_history],
                'Alerts': [len(r['alerts']) for r in st.session_state.aml_history],
                'Amount': [r['total_amount'] for r in st.session_state.aml_history]
            }
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=history_df['Time'],
                y=history_df['Alerts'],
                mode='lines+markers',
                name='Alerts',
                line=dict(color='red', width=2)
            ))
            fig.update_layout(
                title="AML Alert Trends",
                xaxis_title="Time",
                yaxis_title="Alerts",
                height=300
            )
            st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.header("📊 Credit Risk Scoring")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📝 Applicant Information")
        
        # Generate sample data button
        if st.button("🎲 Generate Test Application", key="gen_credit"):
            # Generate realistic credit profile
            good_credit = random.random() > 0.3
            
            if good_credit:
                st.session_state.credit_score = random.randint(700, 850)
                st.session_state.credit_income = random.uniform(50000, 150000)
                st.session_state.credit_debt = random.uniform(5000, 30000)
                st.session_state.credit_history = random.randint(5, 20)
                st.session_state.credit_inquiries = random.randint(0, 2)
            else:
                st.session_state.credit_score = random.randint(500, 650)
                st.session_state.credit_income = random.uniform(25000, 50000)
                st.session_state.credit_debt = random.uniform(30000, 80000)
                st.session_state.credit_history = random.randint(1, 4)
                st.session_state.credit_inquiries = random.randint(5, 10)
        
        applicant_id = st.text_input("Applicant ID", value=f"APP-{random.randint(100000, 999999)}")
        
        col_a, col_b = st.columns(2)
        with col_a:
            existing_score = st.number_input("Existing Credit Score (300-850)", 
                                            value=st.session_state.get('credit_score', 720),
                                            min_value=300, max_value=850)
            annual_income = st.number_input("Annual Income (USD)", 
                                           value=float(st.session_state.get('credit_income', 75000)),
                                           min_value=0.0)
            employment_length = st.slider("Employment Years", 0, 40,
                                         value=int(st.session_state.get('credit_employment', 5)))
        
        with col_b:
            total_debt = st.number_input("Total Debt (USD)", 
                                        value=float(st.session_state.get('credit_debt', 15000)),
                                        min_value=0.0)
            credit_history_length = st.slider("Credit History (years)", 0, 30,
                                             value=int(st.session_state.get('credit_history', 8)))
            num_credit_inquiries = st.slider("Recent Credit Inquiries", 0, 20,
                                            value=int(st.session_state.get('credit_inquiries', 2)))
        
        loan_amount = st.number_input("Loan Amount Requested (USD)", value=25000.0, min_value=1000.0)
        loan_purpose = st.selectbox("Loan Purpose", 
                                    ["home_purchase", "debt_consolidation", "auto", 
                                     "business", "education", "other"])
        
        # Score button
        if st.button("🔍 Assess Credit Risk", type="primary", key="score_credit"):
            # Create application as dictionary
            application = {
                'applicant_id': applicant_id,
                'requested_amount': loan_amount,
                'loan_purpose': loan_purpose,
                'annual_income': annual_income,
                'employment_length_years': employment_length,
                'existing_credit_score': existing_score,
                'total_debt': total_debt,
                'credit_history_length_years': credit_history_length,
                'num_credit_inquiries': num_credit_inquiries,
                'has_mortgage': random.choice([True, False]),
                'has_auto_loan': random.choice([True, False]),
                'num_credit_cards': random.randint(1, 8)
            }
            
            # Run scoring
            score_result = engines['credit'].evaluate_application(applicant_id, application)
            
            # Store in history
            result = {
                'timestamp': datetime.now(),
                'applicant_id': applicant_id,
                'score': score_result,
                'requested_amount': loan_amount
            }
            st.session_state.credit_results_history.append(result)
            try:
                db_manager.save_credit_assessment(result)  # Save to database
            except Exception as e:
                st.warning(f"Failed to save to database: {e}")
            
            st.success(f"✅ Assessment completed! Credit Score: {score_result.score:.0f}")
            st.rerun()  # Refresh to update statistics
    
    with col2:
        st.subheader("📋 Scoring Model")
        st.info("""
        **5C Credit Assessment Model:**
        
        1️⃣ **Character**
        - Credit history
        - Repayment history
        
        2️⃣ **Capacity**
        - Income level
        - Debt-to-income ratio
        
        3️⃣ **Capital**
        - Existing assets
        - Savings
        
        4️⃣ **Collateral**
        - Collateral value
        
        5️⃣ **Conditions**
        - Loan Purpose
        - Market conditions
        
        **Score Range:** 300-850
        """)
    
    # Only display results section if there's history
    if not st.session_state.credit_results_history:
        st.info("""
        👋 **Welcome to Credit Risk Assessment!**
        
        To get started:
        1. Click "🎲 Generate Test Application" to create sample data
        2. Or manually enter applicant details
        3. Click "🔍 Assess Credit Risk" to evaluate
        """)
    
    # Display latest result
    if st.session_state.credit_results_history:
        st.markdown("---")
        st.subheader("🎯 Latest Assessment Results")
        
        latest = st.session_state.credit_results_history[-1]
        score = latest['score']
        
        # Score gauge
        fig = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=score.score,
            domain={'x': [0, 1], 'y': [0, 1]},
            title={'text': "Credit Score", 'font': {'size': 24}},
            delta={'reference': 650, 'increasing': {'color': "green"}},
            gauge={
                'axis': {'range': [300, 850], 'tickwidth': 1, 'tickcolor': "darkblue"},
                'bar': {'color': "darkblue"},
                'bgcolor': "white",
                'borderwidth': 2,
                'bordercolor': "gray",
                'steps': [
                    {'range': [300, 580], 'color': '#ff4444'},
                    {'range': [580, 670], 'color': '#ffbb33'},
                    {'range': [670, 740], 'color': '#00C851'},
                    {'range': [740, 850], 'color': '#007E33'}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': 700
                }
            }
        ))
        fig.update_layout(height=300, margin=dict(l=20, r=20, t=50, b=20))
        st.plotly_chart(fig, use_container_width=True)
        
        # Results
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Credit Score", f"{score.score:.0f}/850")
        with col2:
            decision_emoji = {"APPROVE": "✅", "REJECT": "❌", 
                            "MANUAL_REVIEW": "⚠️", "CONDITIONAL_APPROVE": "✓"}
            st.metric("Decision", f"{decision_emoji.get(score.decision.name, '?')} {score.decision.name.replace('_', ' ').title()}")
        with col3:
            st.metric("Recommended Limit", f"${score.recommended_limit:,.2f}")
        with col4:
            st.metric("Recommended APR", f"{score.recommended_apr:.2f}%")
        
        # Risk factors
        st.subheader("📊 Risk Factor Analysis")
        factors_df = {
            'Factor': list(score.factors.keys()),
            'Weight': [f"{v*100:.0f}%" for v in score.factors.values()]
        }
        
        fig = px.bar(
            x=factors_df['Weight'],
            y=factors_df['Factor'],
            orientation='h',
            title="Credit Risk Factor Weights",
        )
        fig.update_layout(height=300, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
        
        # Score distribution
        if len(st.session_state.credit_results_history) > 1:
            st.markdown("---")
            st.subheader("📊 Historical Score Distribution")
            
            scores = [r['score'].score for r in st.session_state.credit_results_history]
            fig = px.histogram(x=scores, nbins=20, 
                             title="Credit Score Distribution",
                             labels={'x': 'Credit Score', 'y': 'Applications'})
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)

with tab3:
    st.header("🛡️ Insurance Fraud Detection")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📝 Claim Information")
        
        # Generate sample data button
        if st.button("🎲 Generate Test Claim", key="gen_insurance"):
            # Generate suspicious or normal claim
            suspicious = random.random() > 0.6
            
            if suspicious:
                st.session_state.ins_type = random.choice(["auto", "health", "property"])
                st.session_state.ins_amount = random.uniform(50000, 200000)
                st.session_state.ins_policy_age = random.randint(1, 90)
                st.session_state.ins_num_claims = random.randint(3, 10)
            else:
                st.session_state.ins_type = random.choice(["auto", "health", "property"])
                st.session_state.ins_amount = random.uniform(5000, 30000)
                st.session_state.ins_policy_age = random.randint(365, 3650)
                st.session_state.ins_num_claims = random.randint(0, 2)
        
        claim_id = st.text_input("Claim ID", value=f"CLM-{random.randint(100000, 999999)}")
        policy_holder = st.text_input("Policy Holder", value=fake.name())
        
        claim_type = st.selectbox("Claim Type",
                                 ["auto", "health", "property", "life"],
                                 index=["auto", "health", "property", "life"].index(
                                     st.session_state.get('ins_type', 'auto')))
        
        col_a, col_b = st.columns(2)
        with col_a:
            claim_amount = st.number_input("Claim Amount (USD)", 
                                          value=float(st.session_state.get('ins_amount', 15000)),
                                          min_value=0.0)
            incident_date = st.date_input("Incident Date", 
                                         value=datetime.now().date() - timedelta(days=7))
        
        with col_b:
            policy_age_days = st.number_input("Policy Age (days)", 
                                             value=st.session_state.get('ins_policy_age', 365),
                                             min_value=1)
            num_previous_claims = st.slider("Previous Claims", 0, 20,
                                           st.session_state.get('ins_num_claims', 1))
        
        incident_description = st.text_area("Incident Description", 
                                           value=f"{claim_type.capitalize()} incident on {incident_date}")
        
        # Additional witnesses for staged accident detection
        if claim_type == "auto":
            has_witnesses = st.checkbox("Witnesses Present", value=False)
            if has_witnesses:
                num_witnesses = st.slider("Number of Witnesses", 1, 10, 2)
            else:
                num_witnesses = 0
        
        # Detect button
        if st.button("🔍 Run Fraud Detection", type="primary", key="detect_insurance"):
            # Create claim as dictionary
            claim = {
                'claim_id': claim_id,
                'policy_holder_id': policy_holder,
                'claim_type': claim_type,
                'claim_amount': claim_amount,
                'incident_date': datetime.combine(incident_date, datetime.min.time()),
                'submission_date': datetime.now(),
                'incident_description': incident_description,
                'policy_start_date': datetime.now() - timedelta(days=policy_age_days),
                'num_previous_claims': num_previous_claims
            }
            
            # Run detection
            alerts = engines['insurance'].evaluate_claim(claim, {})
            
            # Store in history
            result = {
                'timestamp': datetime.now(),
                'claim_id': claim_id,
                'alerts': alerts,
                'claim_amount': claim_amount,
                'claim_type': claim_type
            }
            st.session_state.insurance_history.append(result)
            try:
                db_manager.save_insurance_claim(result)  # Save to database
            except Exception as e:
                st.warning(f"Failed to save to database: {e}")
            
            st.success(f"✅ Detection completed! Found {len(alerts)} alert(s)")
            st.rerun()  # Refresh to update statistics
    
    with col2:
        st.subheader("📋 Detection Rules")
        st.info("""
        **Active Rules:**
        
        1️⃣ **Staged Accident Detection**
        - Multiple vehicle coordination
        - Witness pattern analysis
        - Injury inconsistency detection
        
        2️⃣ **Medical Billing Fraud**
        - Upcoding detection
        - Unbundling detection
        - Duplicate billing analysis
        
        3️⃣ **Property Value Inflation**
        - Abnormal claim amounts
        - Immediate claims on new policies
        - Frequent claim patterns
        """)
    
    # Only display results section if there's history
    if not st.session_state.insurance_history:
        st.info("""
        👋 **Welcome to Insurance Fraud Detection!**
        
        To get started:
        1. Click "🎲 Generate Test Claim" to create sample data
        2. Or manually enter claim details
        3. Click "🔍 Run Fraud Detection" to analyze
        """)
    
    # Display latest result
    if st.session_state.insurance_history:
        st.markdown("---")
        st.subheader("🚨 Latest Detection Results")
        
        latest = st.session_state.insurance_history[-1]
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Claim Amount", f"${latest['claim_amount']:,.2f}")
        with col2:
            st.metric("Claim Type", latest['claim_type'].upper())
        with col3:
            st.metric("Alerts", len(latest['alerts']))
        with col4:
            risk = "High Risk" if latest['alerts'] else "Normal"
            st.metric("Risk Assessment", risk)
        
        # Display alerts
        if latest['alerts']:
            for alert in latest['alerts']:
                severity_class = f"alert-{alert.severity.lower()}"
                st.markdown(f"""
                <div class="{severity_class}">
                    <strong>🚨 {alert.fraud_type}</strong><br>
                    Severity: {alert.severity} | Confidence: {alert.confidence*100:.1f}%<br>
                    Reason: {alert.reason}<br>
                    Evidence: {', '.join(alert.evidence)}<br>
                    <small>Claim ID: {alert.claim_id}</small>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.success("✅ No fraud indicators detected")
        
        # Claims by type
        if len(st.session_state.insurance_history) > 1:
            st.markdown("---")
            st.subheader("📊 Claims Analysis")
            
            claim_types = [r['claim_type'] for r in st.session_state.insurance_history]
            fraud_counts = [len(r['alerts']) for r in st.session_state.insurance_history]
            
            fig = px.pie(names=claim_types, title="Claim Type Distribution")
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)

with tab4:
    st.header("📈 Market Manipulation Detection")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📝 Trading Activity Monitoring")
        
        # Generate sample data button
        if st.button("🎲 Generate Test Trade", key="gen_market"):
            # Generate suspicious or normal trading
            manipulation_type = random.choice(["pump_dump", "wash_trade", "spoofing", "normal"])
            
            if manipulation_type == "pump_dump":
                st.session_state.mkt_volume = random.uniform(5_000_000, 20_000_000)
                st.session_state.mkt_price_change = random.uniform(30, 80)
                st.session_state.mkt_social = random.uniform(15, 30)
                st.session_state.mkt_market_cap = random.uniform(50_000_000, 300_000_000)
            elif manipulation_type == "wash_trade":
                st.session_state.mkt_volume = random.uniform(2_000_000, 10_000_000)
                st.session_state.mkt_roundtrip = random.randint(15, 40)
                st.session_state.mkt_price_change = random.uniform(-2, 2)
            elif manipulation_type == "spoofing":
                st.session_state.mkt_orders_placed = random.randint(500, 2000)
                st.session_state.mkt_orders_canceled = random.randint(450, 1950)
                st.session_state.mkt_cancel_ratio = 0.85 + random.random() * 0.14
            else:
                st.session_state.mkt_volume = random.uniform(500_000, 2_000_000)
                st.session_state.mkt_price_change = random.uniform(-5, 5)
                st.session_state.mkt_social = random.uniform(0.8, 1.5)
                st.session_state.mkt_market_cap = random.uniform(1_000_000_000, 10_000_000_000)
        
        symbol = st.text_input("Symbol", value="AAPL").upper()
        
        col_a, col_b = st.columns(2)
        with col_a:
            current_price = st.number_input("Current Price (USD)", value=150.0, min_value=0.0)
            trading_volume = st.number_input("Volume", 
                                            value=int(st.session_state.get('mkt_volume', 1_000_000)),
                                            min_value=0)
            price_change_pct = st.slider("24h Price Change %", -100, 100,
                                         int(st.session_state.get('mkt_price_change', 0)))
        
        with col_b:
            avg_30day_volume = st.number_input("30-Day Avg Volume", value=1_500_000, min_value=0)
            market_cap = st.number_input("Market Cap (USD)", 
                                        value=float(st.session_state.get('mkt_market_cap', 1_000_000_000)),
                                        min_value=0.0)
            social_sentiment = st.slider("Social Sentiment Growth", 0.0, 50.0,
                                        float(st.session_state.get('mkt_social', 1.0)))
        
        # Order book data for spoofing detection
        with st.expander("📊 Order Book Data (Advanced)"):
            orders_placed = st.number_input("Orders Placed", 
                                           value=st.session_state.get('mkt_orders_placed', 100),
                                           min_value=0)
            orders_canceled = st.number_input("Orders Canceled", 
                                             value=st.session_state.get('mkt_orders_canceled', 10),
                                             min_value=0)
        
        # Detect button
        if st.button("🔍 Run Manipulation Detection", type="primary", key="detect_market"):
            # Create trading activity as dictionary
            activity = {
                'symbol': symbol,
                'timestamp': datetime.now(),
                'price': current_price,
                'volume': trading_volume,
                'market_cap': market_cap,
                'price_change_24h': price_change_pct / 100,
                'volume_change': trading_volume / avg_30day_volume if avg_30day_volume > 0 else 1.0,
                'social_sentiment_change': social_sentiment,
                'order_book_depth': {"bids": 1000, "asks": 1000},
                'num_trades': random.randint(1000, 10000)
            }
            
            # Run detection
            alerts = engines['market'].evaluate_trade(activity, {})
            
            # Store in history
            result = {
                'timestamp': datetime.now(),
                'symbol': symbol,
                'alerts': alerts,
                'price': current_price,
                'volume': trading_volume
            }
            st.session_state.market_history.append(result)
            try:
                db_manager.save_market_alert(result)  # Save to database
            except Exception as e:
                st.warning(f"Failed to save to database: {e}")
            
            st.success(f"✅ Detection completed! Found {len(alerts)} alert(s)")
            st.rerun()  # Refresh to update statistics
    
    with col2:
        st.subheader("📋 Detection Rules")
        st.info("""
        **Active Rules:**
        
        1️⃣ **Pump & Dump**
        - Abnormal volume spikes
        - Rapid price increases
        - Social media hype
        - Small-cap characteristics
        
        2️⃣ **Wash Trading**
        - Roundtrip trade detection
        - Self-trading detection
        - False liquidity
        
        3️⃣ **Spoofing**
        - Large order cancellations
        - Order book manipulation
        - False market depth
        """)
    
    # Only display results section if there's history
    if not st.session_state.market_history:
        st.info("""
        👋 **Welcome to Market Manipulation Detection!**
        
        To get started:
        1. Click "🎲 Generate Test Trade" to create sample data
        2. Or manually enter trading activity
        3. Click "🔍 Run Manipulation Detection" to analyze
        """)
    
    # Display latest result
    if st.session_state.market_history:
        st.markdown("---")
        st.subheader("🚨 Latest Detection Results")
        
        latest = st.session_state.market_history[-1]
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Symbol", latest['symbol'])
        with col2:
            st.metric("Price", f"${latest['price']:.2f}")
        with col3:
            st.metric("Volume", f"{latest['volume']:,}")
        with col4:
            st.metric("Alerts", len(latest['alerts']))
        
        # Display alerts
        if latest['alerts']:
            for alert in latest['alerts']:
                severity_class = f"alert-{alert.severity.lower()}"
                st.markdown(f"""
                <div class="{severity_class}">
                    <strong>🚨 {alert.manipulation_type.upper()}</strong><br>
                    Severity: {alert.severity} | Confidence: {alert.confidence*100:.1f}%<br>
                    Reason: {alert.reason}<br>
                    Estimated Impact: ${alert.estimated_impact:,.2f}<br>
                    Recommended Action: {alert.recommended_action}<br>
                    <small>Symbol: {alert.symbol} | Time: {alert.timestamp.strftime('%Y-%m-%d %H:%M')}</small>
                </div>
                """, unsafe_allow_html=True)
            
            # Alert evidence details
            with st.expander("📋 Evidence Details"):
                for alert in latest['alerts']:
                    st.write(f"**{alert.manipulation_type}:**")
                    for evidence in alert.evidence:
                        st.write(f"- {evidence}")
        else:
            st.success("✅ No market manipulation detected")
        
        # Price and volume chart
        if len(st.session_state.market_history) > 1:
            st.markdown("---")
            st.subheader("📊 Market Trends")
            
            history_data = st.session_state.market_history[-20:]  # Last 20 records
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=[r['timestamp'] for r in history_data],
                y=[r['price'] for r in history_data],
                name='Price',
                yaxis='y1',
                line=dict(color='blue')
            ))
            fig.add_trace(go.Bar(
                x=[r['timestamp'] for r in history_data],
                y=[r['volume'] for r in history_data],
                name='Volume',
                yaxis='y2',
                opacity=0.3
            ))
            
            fig.update_layout(
                title=f"{latest['symbol']} Price & Volume",
                yaxis=dict(title='Price (USD)', side='left'),
                yaxis2=dict(title='Volume', overlaying='y', side='right'),
                height=400
            )
            st.plotly_chart(fig, use_container_width=True)

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: gray;'>
    <p>🏦 Unified Financial Detection Platform v2.0</p>
    <p>Powered by Lambda Architecture | Real-time + Batch Processing</p>
    <p>⚡ Supports AML, Credit Risk, Insurance Fraud, Market Manipulation</p>
</div>
""", unsafe_allow_html=True)
