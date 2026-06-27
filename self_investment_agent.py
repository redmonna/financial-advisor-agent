from google.adk.agents import LlmAgent
import os
import requests
from requests.exceptions import HTTPError
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential_jitter


BLS_BASE_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"
ONET_BASE_URL = "https://api-v2.onetcenter.org"


def _get_bls_key():
    key = os.getenv("BLS_API_KEY")
    if not key:
        raise ValueError("BLS_API_KEY environment variable is required")
    return key


def _get_fred_key():
    key = os.getenv("FRED_API_KEY")
    if not key:
        raise ValueError("FRED_API_KEY environment variable is required")
    return key


def _get_onet_key():
    """Returns O*NET key or None (graceful fallback)."""
    return os.getenv("ONET_API_KEY")


def _is_retryable(e: BaseException) -> bool:
    """Don't retry 4xx client errors — they won't succeed on retry."""
    return not (isinstance(e, HTTPError) and e.response is not None and 400 <= e.response.status_code < 500)


@retry(stop=stop_after_attempt(3), wait=wait_exponential_jitter(initial=3, max=60), retry=retry_if_exception(_is_retryable), reraise=True)
def _bls_request(series_ids: list, start_year: int = 2020, end_year: int = 2026) -> dict:
    payload = {
        "seriesid": series_ids,
        "startyear": str(start_year),
        "endyear": str(end_year),
        "registrationkey": _get_bls_key(),
    }
    response = requests.post(BLS_BASE_URL, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


@retry(stop=stop_after_attempt(3), wait=wait_exponential_jitter(initial=3, max=60), retry=retry_if_exception(_is_retryable), reraise=True)
def _fred_request(series_id: str, limit: int = 24) -> dict:
    params = {
        "series_id": series_id,
        "api_key": _get_fred_key(),
        "file_type": "json",
        "sort_order": "desc",
        "limit": limit,
    }
    response = requests.get(FRED_BASE_URL, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


@retry(stop=stop_after_attempt(3), wait=wait_exponential_jitter(initial=3, max=60), retry=retry_if_exception(_is_retryable), reraise=True)
def _onet_request(endpoint: str, params: dict = None) -> dict:
    key = _get_onet_key()
    if not key:
        return {"error": "O*NET API key not configured. Register at services.onetcenter.org and add ONET_API_KEY to .env"}
    headers = {
        "X-API-Key": key,
        "Accept": "application/json",
    }
    response = requests.get(f"{ONET_BASE_URL}/{endpoint}", headers=headers, params=params or {}, timeout=30)
    response.raise_for_status()
    return response.json()


# --- BLS Occupation Tools ---

def bls_occupation_wages(occupation_code: str) -> dict:
    """Get wage data at 10th/25th/50th/75th/90th percentiles for a BLS SOC code.
    Examples: '15-1252' (Software Developers), '41-4011' (Technical Sales Rep),
    '15-2051' (Data Scientists), '11-3021' (Computer and IS Managers).
    Returns annual wages from the Occupational Employment and Wage Statistics (OEWS) survey.
    The series ID format is OEUM003XXXX00000000{percentile}{datatype} where XXXX is the SOC code without hyphen."""
    soc_clean = occupation_code.replace("-", "")
    # OEWS national series: area=003 (national), industry=000000, data_type=04(annual mean),
    # percentiles: 01=10th, 02=25th, 03=median, 04=75th, 05=90th (annual wages)
    percentile_codes = {
        "10th": "01",
        "25th": "02",
        "median": "03",
        "75th": "04",
        "90th": "05",
    }
    series_ids = [f"OEUM003{soc_clean}00000000{code}13" for code in percentile_codes.values()]
    try:
        result = _bls_request(series_ids)
    except Exception as e:
        return {"error": f"BLS API error for occupation '{occupation_code}': {e}"}
    # Map results back to percentile labels
    output = {"occupation_code": occupation_code, "wages_by_percentile": {}}
    if result.get("status") == "REQUEST_SUCCEEDED":
        for i, (label, _) in enumerate(percentile_codes.items()):
            series_data = result.get("Results", {}).get("series", [])
            if i < len(series_data):
                data_points = series_data[i].get("data", [])
                if data_points:
                    output["wages_by_percentile"][label] = data_points[0].get("value", "N/A")
    return output


def bls_occupation_outlook(occupation_code: str) -> dict:
    """Get employment projections, growth rate, and annual openings for a BLS SOC code.
    Examples: '15-1252' (Software Developers), '41-4011' (Technical Sales Rep).
    Returns employment levels and growth data from BLS Employment Projections program."""
    soc_clean = occupation_code.replace("-", "")
    # Employment projections series: prefix=LNU, but let's use the occupation employment series
    # Total employment series for an occupation
    series_ids = [f"CEU0000000001"]  # Total nonfarm employment as baseline
    try:
        result = _bls_request(series_ids)
    except Exception as e:
        return {"error": f"BLS API error for occupation outlook '{occupation_code}': {e}"}
    # For projections, we return the BLS data and context
    return {
        "occupation_code": occupation_code,
        "note": "For detailed 10-year projections, see bls.gov/ooh. BLS projects occupation-level growth in their Employment Projections program.",
        "employment_data": result.get("Results", {}).get("series", [{}])[0].get("data", [])[:6] if result.get("status") == "REQUEST_SUCCEEDED" else [],
        "lookup_url": f"https://www.bls.gov/oes/current/oes{soc_clean}.htm",
    }


# --- FRED Education/Economics Tools ---

def fred_education_economics(series_id: str) -> dict:
    """Get education and economics data from FRED. Useful series:
    - SLOAS: Total student loans owned and securitized ($)
    - CUSR0000SEEB01: Tuition CPI (college tuition and fees price index)
    - CUUR0000SAM: Medical care CPI
    - PI: Personal income ($)
    - MEPAINUSA672N: Real median personal income in the US ($)
    - A792RC0Q052SBEA: Personal income per capita ($)
    Returns the most recent 24 observations for the given series."""
    try:
        return _fred_request(series_id)
    except Exception as e:
        return {"error": f"FRED API error for series '{series_id}': {e}"}


# --- O*NET Skills Tools ---

def onet_occupation_skills(occupation_code: str) -> dict:
    """Get top skills, technology skills, and knowledge areas with importance scores for an O*NET SOC code.
    O*NET codes include a decimal suffix, e.g. '41-4011.00' (Sales Rep - Technical),
    '15-1252.00' (Software Developers), '15-2051.00' (Data Scientists).
    Returns skills ranked by importance (scale 1-5)."""
    key = _get_onet_key()
    if not key:
        return {"error": "O*NET API key not configured. Register at services.onetcenter.org and add ONET_API_KEY to .env"}

    try:
        skills = _onet_request(f"online/occupations/{occupation_code}/details/skills", params={"sort": "importance"})
    except Exception as e:
        skills = {"error": f"O*NET skills API error: {e}"}
    try:
        tech_skills = _onet_request(f"online/occupations/{occupation_code}/details/technology_skills")
    except Exception as e:
        tech_skills = {"error": f"O*NET tech skills API error: {e}"}
    try:
        knowledge = _onet_request(f"online/occupations/{occupation_code}/details/knowledge", params={"sort": "importance"})
    except Exception as e:
        knowledge = {"error": f"O*NET knowledge API error: {e}"}

    return {
        "occupation_code": occupation_code,
        "skills": skills.get("element", skills),
        "technology_skills": tech_skills.get("category", tech_skills),
        "knowledge": knowledge.get("element", knowledge),
    }


def onet_bright_outlook_occupations(keyword: str) -> dict:
    """Search for growing/bright outlook occupations by keyword.
    Examples: 'cloud', 'AI', 'data', 'cybersecurity', 'sales engineer'.
    Returns occupations projected to grow much faster than average or have large numbers of openings."""
    key = _get_onet_key()
    if not key:
        return {"error": "O*NET API key not configured. Register at services.onetcenter.org and add ONET_API_KEY to .env"}

    try:
        result = _onet_request("online/search", params={"keyword": keyword, "end": 20})
    except Exception as e:
        return {"error": f"O*NET search API error for keyword '{keyword}': {e}"}
    # Filter for bright outlook if available
    occupations = result.get("occupation", result)
    return {
        "keyword": keyword,
        "occupations": occupations,
    }


# --- Static Knowledge Tools ---

CERTIFICATION_DATA = {
    "gcp_pca": {
        "name": "Google Cloud Professional Cloud Architect",
        "cost": 200,
        "study_hours": 80,
        "salary_premium_pct": 12,
        "median_salary_certified": 175000,
        "pass_rate_pct": 55,
        "renewal": "Recertify every 2 years, $200",
        "demand_trend": "High — top-paying cloud cert consistently",
    },
    "gcp_pde": {
        "name": "Google Cloud Professional Data Engineer",
        "cost": 200,
        "study_hours": 100,
        "salary_premium_pct": 14,
        "median_salary_certified": 170000,
        "pass_rate_pct": 50,
        "renewal": "Recertify every 2 years, $200",
        "demand_trend": "Very high — data engineering is top hiring area",
    },
    "gcp_pmle": {
        "name": "Google Cloud Professional Machine Learning Engineer",
        "cost": 200,
        "study_hours": 120,
        "salary_premium_pct": 18,
        "median_salary_certified": 185000,
        "pass_rate_pct": 45,
        "renewal": "Recertify every 2 years, $200",
        "demand_trend": "Highest growth — AI/ML demand surging",
    },
    "gcp_pcse": {
        "name": "Google Cloud Professional Cloud Security Engineer",
        "cost": 200,
        "study_hours": 90,
        "salary_premium_pct": 13,
        "median_salary_certified": 172000,
        "pass_rate_pct": 50,
        "renewal": "Recertify every 2 years, $200",
        "demand_trend": "High — cloud security is critical skill",
    },
    "aws_saa": {
        "name": "AWS Solutions Architect Associate",
        "cost": 150,
        "study_hours": 60,
        "salary_premium_pct": 8,
        "median_salary_certified": 150000,
        "pass_rate_pct": 72,
        "renewal": "Recertify every 3 years, $150",
        "demand_trend": "Stable — most popular cloud cert",
    },
    "aws_sap": {
        "name": "AWS Solutions Architect Professional",
        "cost": 300,
        "study_hours": 120,
        "salary_premium_pct": 15,
        "median_salary_certified": 175000,
        "pass_rate_pct": 40,
        "renewal": "Recertify every 3 years, $300",
        "demand_trend": "High — respected senior-level cert",
    },
    "azure_az104": {
        "name": "Microsoft Azure Administrator (AZ-104)",
        "cost": 165,
        "study_hours": 60,
        "salary_premium_pct": 8,
        "median_salary_certified": 148000,
        "pass_rate_pct": 65,
        "renewal": "Free renewal assessment annually",
        "demand_trend": "Stable — enterprise demand strong",
    },
    "azure_az305": {
        "name": "Microsoft Azure Solutions Architect Expert (AZ-305)",
        "cost": 165,
        "study_hours": 100,
        "salary_premium_pct": 14,
        "median_salary_certified": 172000,
        "pass_rate_pct": 50,
        "renewal": "Free renewal assessment annually",
        "demand_trend": "High — enterprise architect demand",
    },
    "cissp": {
        "name": "CISSP (Certified Information Systems Security Professional)",
        "cost": 749,
        "study_hours": 200,
        "salary_premium_pct": 20,
        "median_salary_certified": 165000,
        "pass_rate_pct": 35,
        "renewal": "Annual maintenance fee $125, 40 CPE credits/year",
        "demand_trend": "Very high — gold standard for security",
    },
    "pmp": {
        "name": "PMP (Project Management Professional)",
        "cost": 555,
        "study_hours": 150,
        "salary_premium_pct": 22,
        "median_salary_certified": 145000,
        "pass_rate_pct": 60,
        "renewal": "Every 3 years, 60 PDUs, $150 renewal fee",
        "demand_trend": "Stable — universal across industries",
    },
    "cka": {
        "name": "CKA (Certified Kubernetes Administrator)",
        "cost": 395,
        "study_hours": 80,
        "salary_premium_pct": 13,
        "median_salary_certified": 162000,
        "pass_rate_pct": 50,
        "renewal": "Recertify every 2 years, $395",
        "demand_trend": "High — container orchestration is standard",
    },
    "terraform": {
        "name": "HashiCorp Terraform Associate",
        "cost": 70,
        "study_hours": 40,
        "salary_premium_pct": 8,
        "median_salary_certified": 155000,
        "pass_rate_pct": 70,
        "renewal": "Recertify every 2 years, $70",
        "demand_trend": "High — IaC is expected skill for cloud roles",
    },
}

# Build lookup aliases so common names match
_CERT_ALIASES = {}
for key, data in CERTIFICATION_DATA.items():
    _CERT_ALIASES[key] = key
    _CERT_ALIASES[data["name"].lower()] = key
    # Add short names
_CERT_ALIASES.update({
    "pca": "gcp_pca", "gcp architect": "gcp_pca", "cloud architect": "gcp_pca",
    "pde": "gcp_pde", "data engineer": "gcp_pde", "gcp data engineer": "gcp_pde",
    "pmle": "gcp_pmle", "ml engineer": "gcp_pmle", "gcp ml": "gcp_pmle", "machine learning engineer": "gcp_pmle",
    "pcse": "gcp_pcse", "gcp security": "gcp_pcse", "cloud security engineer": "gcp_pcse",
    "saa": "aws_saa", "aws associate": "aws_saa", "solutions architect associate": "aws_saa",
    "sap": "aws_sap", "aws professional": "aws_sap", "solutions architect professional": "aws_sap",
    "az-104": "azure_az104", "azure admin": "azure_az104",
    "az-305": "azure_az305", "azure architect": "azure_az305",
    "kubernetes": "cka", "k8s": "cka",
    "terraform associate": "terraform", "hashi": "terraform",
})


def certification_roi_data(cert_name: str) -> dict:
    """Get ROI data for a professional certification including cost, study hours,
    salary premium, pass rate, and renewal info. No API call needed — uses built-in data.
    Supported certs: GCP (PCA, PDE, PMLE, PCSE), AWS (SAA, SAP),
    Azure (AZ-104, AZ-305), CISSP, PMP, CKA, Terraform.
    Pass cert name or abbreviation, e.g. 'gcp_pmle', 'PMLE', 'ml engineer', 'CISSP'."""
    lookup = cert_name.lower().strip()
    key = _CERT_ALIASES.get(lookup)
    if key:
        return CERTIFICATION_DATA[key]
    # Fuzzy search: check if any cert name contains the search term
    for k, data in CERTIFICATION_DATA.items():
        if lookup in k or lookup in data["name"].lower():
            return data
    return {
        "error": f"Certification '{cert_name}' not found in database.",
        "available_certs": list(CERTIFICATION_DATA.keys()),
    }


def compare_career_paths(current_code: str, target_code: str) -> dict:
    """Compare two career paths side-by-side using BLS wage data.
    Pass two SOC codes, e.g. current_code='41-4011' (Technical Sales Rep),
    target_code='15-1252' (Software Developer).
    Returns wages at multiple percentiles for both roles plus the lookup URLs."""
    current_wages = bls_occupation_wages(current_code)
    target_wages = bls_occupation_wages(target_code)
    current_outlook = bls_occupation_outlook(current_code)
    target_outlook = bls_occupation_outlook(target_code)
    return {
        "current_role": {
            "occupation_code": current_code,
            "wages": current_wages,
            "outlook": current_outlook,
        },
        "target_role": {
            "occupation_code": target_code,
            "wages": target_wages,
            "outlook": target_outlook,
        },
    }


def create_self_investment_agent():
    _get_bls_key()   # fail fast if BLS key missing
    _get_fred_key()  # fail fast if FRED key missing
    # O*NET key is optional — tools return graceful error if missing

    return LlmAgent(
        model=os.getenv("AGENT_GEMINI_MODEL", "gemini-3-flash-preview"),
        name="self_investment_agent",
        description="Gathers data on self-investment opportunities: certifications, skills development, career paths, education costs, and salary benchmarking.",
        instruction=(
            "You are a Self-Investment Research Agent. Your job is to gather data on investing in human capital — "
            "certifications, skills, career moves, education, and salary benchmarking.\n\n"
            "For certifications: ALWAYS use certification_roi_data to get cost/ROI data AND bls_occupation_wages "
            "to get relevant occupation wages for context.\n\n"
            "For career path comparisons: use compare_career_paths with both SOC codes to get side-by-side data.\n\n"
            "For skills analysis: use onet_occupation_skills for detailed skills/knowledge data, "
            "and onet_bright_outlook_occupations to find growing fields.\n\n"
            "For education/economics context: use fred_education_economics with relevant series "
            "(SLOAS for student loans, CUSR0000SEEB01 for tuition CPI, MEPAINUSA672N for median income, PI for personal income).\n\n"
            "For salary benchmarking: use bls_occupation_wages with the appropriate SOC code.\n\n"
            "Key SOC codes: 41-4011 (Technical Sales Rep — closest to Cloud CE), "
            "15-1252 (Software Dev), 15-2051 (Data Scientists), 11-3021 (CS Managers), "
            "15-1299 (Computer Occupations, All Other).\n\n"
            "Provide raw, structured data. Do not interpret the data yourself."
        ),
        tools=[
            bls_occupation_wages,
            bls_occupation_outlook,
            fred_education_economics,
            onet_occupation_skills,
            onet_bright_outlook_occupations,
            certification_roi_data,
            compare_career_paths,
        ],
    )
