import os
import requests
import json
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from anthropic import Anthropic
import time

# Import models from main.py
from main import Base, RegulatoryChange, UserReport, User, UserPreference, DocumentType

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/regtracker")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Database setup
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Anthropic client
anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)

# EUR-Lex SPARQL endpoint
EURLEX_SPARQL_ENDPOINT = "https://publications.europa.eu/webapi/rdf/sparql"

def query_eurlex_recent_documents(days_back=30):
    """Query EUR-Lex for recent regulatory documents"""
    
    start_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    
    # SPARQL query to get recent EU regulations and directives
    sparql_query = f"""
    PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
    
    SELECT DISTINCT ?work ?title ?date ?celex ?type
    WHERE {{
        ?work cdm:work_date_document ?date .
        ?work cdm:resource_legal_id_celex ?celex .
        ?work cdm:work_has_expression ?expr .
        ?expr cdm:expression_title ?title .
        ?work cdm:resource_legal_is_about_concept_resource-type ?typeUri .
        ?typeUri skos:prefLabel ?type .
        
        FILTER (?date >= "{start_date}"^^xsd:date)
        FILTER (LANG(?title) = "en")
        FILTER (LANG(?type) = "en")
        FILTER (CONTAINS(LCASE(?type), "regulation") || CONTAINS(LCASE(?type), "directive") || CONTAINS(LCASE(?type), "decision"))
    }}
    ORDER BY DESC(?date)
    LIMIT 50
    """
    
    try:
        response = requests.post(
            EURLEX_SPARQL_ENDPOINT,
            data={"query": sparql_query},
            headers={"Accept": "application/json"},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            results = []
            
            for binding in data.get("results", {}).get("bindings", []):
                result = {
                    "work_uri": binding["work"]["value"],
                    "title": binding["title"]["value"],
                    "date": binding["date"]["value"],
                    "celex": binding["celex"]["value"],
                    "type": binding["type"]["value"]
                }
                results.append(result)
            
            return results
        else:
            print(f"EUR-Lex query failed: {response.status_code}")
            return []
            
    except Exception as e:
        print(f"Error querying EUR-Lex: {e}")
        return []

def store_regulatory_change(db, document):
    """Store a regulatory change in the database"""
    
    # Check if already exists
    existing = db.query(RegulatoryChange).filter(
        RegulatoryChange.cellar_id == document["celex"]
    ).first()
    
    if existing:
        return existing
    
    # Determine document type
    doc_type = DocumentType.legislation
    if "directive" in document["type"].lower():
        doc_type = DocumentType.legislation
    elif "regulation" in document["type"].lower():
        doc_type = DocumentType.legislation
    elif "decision" in document["type"].lower():
        doc_type = DocumentType.legislation
    
    # Create new regulatory change
    reg_change = RegulatoryChange(
        title=document["title"],
        jurisdiction="EU",
        document_type=doc_type,
        publication_date=datetime.fromisoformat(document["date"]),
        source_url=f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{document['celex']}",
        source_name="EUR-Lex",
        cellar_id=document["celex"],
        raw_text=document["title"]  # In production, fetch full text
    )
    
    db.add(reg_change)
    db.commit()
    db.refresh(reg_change)
    
    return reg_change

def analyze_relevance_with_llm(document, user_sector, user_jurisdiction):
    """Use Claude to analyze document relevance for a specific sector"""
    
    prompt = f"""You are a legal compliance analyst helping businesses understand regulatory changes.

**Document Information:**
- Title: {document['title']}
- Jurisdiction: EU
- Publication Date: {document['date']}
- Source: EUR-Lex (CELEX: {document['celex']})

**User Context:**
- Sector: {user_sector}
- Jurisdiction: {user_jurisdiction}

**Task:**
Analyze this regulatory change and provide:

1. A 3-5 bullet point summary in plain English (avoid legal jargon)
2. An explanation of why this may matter for businesses in the {user_sector} sector
3. Key business areas potentially impacted (select from: IT, HR, Finance, Operations, Governance, Data Protection, Reporting)
4. A relevance score (0-1) indicating how directly this affects {user_sector} businesses

**Important:**
- Use cautious language: "may impact", "potential relevance", "review recommended"
- Do not provide legal advice or definitive compliance conclusions
- If the document is not relevant to {user_sector}, explain why briefly and give a low score

**Output Format (JSON):**
{{
  "summary": ["bullet 1", "bullet 2", ...],
  "relevance_explanation": "...",
  "key_impacts": ["IT", "Data Protection"],
  "relevance_score": 0.85
}}

Respond ONLY with valid JSON, no additional text."""

    try:
        message = anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        response_text = message.content[0].text
        
        # Extract JSON from response
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1
        
        if json_start >= 0 and json_end > json_start:
            json_str = response_text[json_start:json_end]
            analysis = json.loads(json_str)
            return analysis
        else:
            print("Could not extract JSON from LLM response")
            return None
            
    except Exception as e:
        print(f"Error analyzing with LLM: {e}")
        return None

def generate_reports_for_users(db, reg_change):
    """Generate personalized reports for users based on their preferences"""
    
    users = db.query(User).filter(User.is_active == True).all()
    
    for user in users:
        if not user.preferences:
            continue
        
        # Check if user's jurisdiction matches
        if user.preferences.jurisdiction != "EU":
            continue
        
        # Check if any user sectors are relevant
        user_sectors = user.preferences.sectors or []
        
        for sector in user_sectors:
            # Analyze relevance with LLM
            analysis = analyze_relevance_with_llm(
                {
                    "title": reg_change.title,
                    "date": reg_change.publication_date.isoformat(),
                    "celex": reg_change.cellar_id
                },
                sector,
                user.preferences.jurisdiction
            )
            
            if not analysis:
                continue
            
            # Only create report if relevance score is above threshold
            if analysis.get("relevance_score", 0) >= 0.3:
                # Check if report already exists
                existing_report = db.query(UserReport).filter(
                    UserReport.user_id == user.id,
                    UserReport.regulatory_change_id == reg_change.id
                ).first()
                
                if not existing_report:
                    report = UserReport(
                        user_id=user.id,
                        regulatory_change_id=reg_change.id,
                        summary=analysis.get("summary", []),
                        relevance_explanation=analysis.get("relevance_explanation", ""),
                        key_impacts=analysis.get("key_impacts", []),
                        relevance_score=analysis.get("relevance_score", 0.0)
                    )
                    db.add(report)
                    print(f"Created report for user {user.email} - relevance: {analysis.get('relevance_score')}")
            
            # Rate limiting - small delay between LLM calls
            time.sleep(1)
        
        db.commit()

def run_monitoring_job():
    """Main monitoring job - runs daily"""
    
    print(f"Starting EUR-Lex monitoring job at {datetime.now()}")
    
    db = SessionLocal()
    
    try:
        # Query EUR-Lex for recent documents
        print("Querying EUR-Lex for recent documents...")
        documents = query_eurlex_recent_documents(days_back=30)
        print(f"Found {len(documents)} documents")
        
        # Process each document
        for doc in documents:
            print(f"\nProcessing: {doc['title'][:80]}...")
            
            # Store regulatory change
            reg_change = store_regulatory_change(db, doc)
            
            # Generate reports for affected users
            if reg_change:
                print("Generating user reports...")
                generate_reports_for_users(db, reg_change)
        
        print(f"\nMonitoring job completed at {datetime.now()}")
        
    except Exception as e:
        print(f"Error in monitoring job: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    run_monitoring_job()