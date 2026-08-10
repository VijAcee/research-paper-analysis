from pydantic import BaseModel, Field, HttpUrl
from datetime import datetime
from typing import List, Dict, Optional, Any

class GlossaryItem(BaseModel):
    term: str
    definition: str

class AbstractSentenceBreakdown(BaseModel):
    sentence: str
    simplified: str
    importance: str

class NaturalNarrativeSection(BaseModel):
    section_title: str
    what_is_happening: str
    why_doing_this: str
    what_trying_to_establish: str
    evidence_provided: str
    result_meaning: str
    why_it_matters: str
    what_not_to_conclude: str

class EquationItem(BaseModel):
    equation: str
    variables: str
    usage: str
    importance: str

class AlgorithmItem(BaseModel):
    title: str
    pseudocode: str
    step_by_step: str

class QuestionItem(BaseModel):
    question: str
    answer: str
    options: Optional[List[str]] = None
    difficulty: Optional[str] = "Medium"

class FlashcardItem(BaseModel):
    question: str
    answer: str
    difficulty: str = "Medium"
    topic: str = "General"

class SimilarPaperItem(BaseModel):
    title: str
    authors: List[str] = []
    year: Optional[int] = None
    url: Optional[str] = None
    similarity_reason: str = ""

class StrengthWeaknessItem(BaseModel):
    category: str
    strength: str
    weakness: str

class AIAnalysis(BaseModel):
    # Professor Mentor Analysis (13 Sections)
    what_is_paper_about: str = Field("", description="2-3 simple sentences explaining topic in 10s")
    why_research_needed: str = Field("", description="Problem, importance, who is affected in plain English")
    explain_like_12: str = Field("", description="Analogies with zero math or technical jargon")
    main_idea: str = Field("", description="Single paragraph: built, different, better")
    how_it_works_steps: List[Dict[str, str]] = Field(default_factory=list, description="Step 1 -> Step 2 pipeline")
    important_terms: List[Dict[str, str]] = Field(default_factory=list, description="Terms with plain analogies")
    what_researchers_discovered: str = Field("", description="Plain English outcomes without raw stats")
    why_is_this_important: str = Field("", description="Impact on doctors, engineers, students, society")
    advantages_explained: List[Dict[str, str]] = Field(default_factory=list, description="Title + multi-sentence explanation")
    limitations_explained: List[Dict[str, str]] = Field(default_factory=list, description="Honest or possible limitations")
    real_life_example: str = Field("", description="Practical real-world scenario")
    key_takeaways_simple: List[str] = Field(default_factory=list, description="5 simple bullet points")
    one_line_summary: str = Field("", description="Single concluding sentence")
    
    # Metadata & Information
    affiliations: List[str] = Field(default_factory=list, description="Author academic/corporate affiliations")
    journal: Optional[str] = Field(None, description="Journal or Conference name")
    publisher: Optional[str] = Field(None, description="Publisher name")
    pages_count: Optional[int] = Field(None, description="Total pages")
    # Universal Domain & Subject Metadata
    research_domain: str = Field("General Academic Discipline", description="Detected Academic Discipline (e.g. Medicine, Organic Chemistry, Law, Civil Engineering, Physics, Economics)")
    subject_area: str = Field("General Study", description="Specific Subject Area (e.g. Oncology, Structural Mechanics, Monetary Policy, Genetics)")
    primary_topic: str = Field("", description="Primary topic of the paper")
    research_problem: str = Field("", description="Core research problem addressed")
    type_of_research: str = Field("Empirical Study", description="Type of Research (Experimental, Clinical Trial, Survey, Theoretical, Case Study, Simulation, Review)")
    domain_confidence: float = Field(0.95, description="Confidence score for domain detection (0.0 to 1.0)")
    domain_explanation_style: str = Field("Specialist Professor & Academic Mentor", description="Adapted teaching persona")
    is_domain_confident: bool = Field(True, description="Whether domain identification was confident")
    
    research_area: str = Field("General Research", description="Specific research area")
    
    # Executive & Abstract Summaries
    executive_summary: str = Field(..., description="400-700 word comprehensive executive summary")
    abstract_summary: str = Field(..., description="Concise abstract overview")
    abstract_breakdown: List[AbstractSentenceBreakdown] = Field(default_factory=list, description="Sentence by sentence breakdown")
    natural_narrative_sections: List[NaturalNarrativeSection] = Field(default_factory=list, description="Coherent, section-level natural narrative breakdown answering core conceptual questions rather than sentence-by-sentence paraphrasing")
    
    # Multi-Tier Explanations
    eli10: str = Field(..., description="Explain Like I'm 10 using simple analogies")
    simplified_explanation: str = Field(..., description="Explain Like I'm a Beginner (ELI5)")
    eli_beginner: Dict[str, str] = Field(default_factory=dict, description="Problem, Method, Result, Conclusion")
    technical_explanation: str = Field(..., description="Explain Like an Engineer")
    eli_engineer: Dict[str, str] = Field(default_factory=dict, description="Algorithms, Architecture, Training, Evaluation, Implementation, Optimization, Limitations")
    
    # Core Research Details
    research_objective: str = Field(..., description="Primary objective")
    problem_statement: str = Field(..., description="Problem statement and who benefits")
    research_motivation: str = Field(..., description="Why authors worked on this, gap, previous work")
    background: str = Field(..., description="Domain background")
    methodology: str = Field(..., description="Step by step methodology")
    model_architecture: str = Field(..., description="Visual architecture explanation")
    dataset_information: str = Field(..., description="Dataset name, source, size, splits, advantages, limitations")
    algorithms_used: str = Field(..., description="Algorithms and equations employed")
    experimental_design: str = Field(..., description="Experimental design and metrics")
    
    # Extracted Math & Algorithms
    equations_breakdown: List[EquationItem] = Field(default_factory=list, description="Equations with variable definitions")
    algorithm_pseudocode: List[AlgorithmItem] = Field(default_factory=list, description="Pseudocode and step explanations")
    
    # Experimental Results & Benchmarks
    experimental_results: Dict[str, Any] = Field(default_factory=dict, description="Accuracy, Precision, Recall, F1, Loss, Latency, Training/Inference time")
    key_findings: List[str] = Field(default_factory=list, description="Key outcomes")
    major_contributions: List[str] = Field(default_factory=list, description="Primary novel contributions")
    advantages: List[str] = Field(default_factory=list, description="Advantages")
    limitations: List[str] = Field(default_factory=list, description="Limitations and weaknesses")
    research_gaps: List[str] = Field(default_factory=list, description="Unresolved gaps")
    future_scope: List[str] = Field(default_factory=list, description="Future research directions")
    practical_applications: List[str] = Field(default_factory=list, description="Real-world use cases")
    references_analysis: List[str] = Field(default_factory=list, description="Most influential references and why cited")
    
    # Keywords
    keywords: List[str] = Field(default_factory=list, description="Technical, Research, and Trending keywords")
    glossary: List[GlossaryItem] = Field(default_factory=list, description="Technical glossary")
    reading_time_minutes: int = Field(12, description="Estimated reading time")
    prerequisite_knowledge: List[str] = Field(default_factory=list, description="Required background knowledge")
    
    # Interactive & Visual Tools
    ai_questions: Dict[str, List[QuestionItem]] = Field(default_factory=dict, description="Interview, Viva, MCQ, Short, Long questions")
    flashcards: List[FlashcardItem] = Field(default_factory=list, description="Interactive flashcards")
    study_notes: Dict[str, str] = Field(default_factory=dict, description="Chapter-wise, Bullet, Revision, One-page notes")
    mind_map_nodes: List[Dict[str, Any]] = Field(default_factory=list, description="Mind map node graph")
    research_timeline: List[Dict[str, str]] = Field(default_factory=list, description="Problem -> Research -> Experiment -> Results -> Conclusion")
    research_workflow: List[Dict[str, str]] = Field(default_factory=list, description="Input -> Processing -> Training -> Testing -> Evaluation -> Output")
    strength_vs_weakness: List[StrengthWeaknessItem] = Field(default_factory=list, description="Comparison matrix")
    similar_papers: List[SimilarPaperItem] = Field(default_factory=list, description="10 recommended similar papers")

    # Master Prompt 30-Section Analysis Additions
    expected_vs_actual_results: List[Dict[str, str]] = Field(default_factory=list, description="Hypothesis comparison table: Expected | Actual | Supported?")
    surprising_findings: List[str] = Field(default_factory=list, description="Surprising or counterintuitive findings")
    author_acknowledged_limitations: List[str] = Field(default_factory=list, description="Limitations explicitly acknowledged by the authors")
    critical_analysis_limitations: List[str] = Field(default_factory=list, description="Additional limitations identified through critical analysis")
    methodological_concerns: List[str] = Field(default_factory=list, description="Methodological concerns (sampling, bias, confounding, causality)")
    interpretation_concerns: List[str] = Field(default_factory=list, description="Concerns about overclaiming or conclusions exceeding evidence")
    alternative_explanations: List[str] = Field(default_factory=list, description="Alternative explanations for observed findings")
    claim_vs_evidence: List[Dict[str, str]] = Field(default_factory=list, description="Claim vs Evidence check with support strength classification")
    contribution_novelty: str = Field("", description="Clear statement of what the paper adds to the field")
    what_paper_does_not_prove: List[str] = Field(default_factory=list, description="Boundaries of conclusions and what cannot be inferred")
    important_numbers_facts: List[Dict[str, str]] = Field(default_factory=list, description="Compact list of essential numbers and facts worth remembering")
    paper_at_a_glance: Dict[str, str] = Field(default_factory=dict, description="12-item summary table (Question, Problem, Gap, Method, Finding, etc.)")
    must_know_points: List[str] = Field(default_factory=list, description="5-10 non-negotiable must-know points")
    remember_5_things: List[str] = Field(default_factory=list, description="5 essential ideas for exams, vivas, interviews, and presentations")
    categorized_questions: Dict[str, List[QuestionItem]] = Field(default_factory=dict, description="Basic, Methodology, Results, Critical thinking, Advanced questions")
    final_takeaway: str = Field("", description="Central message on what the reader should actually believe/understand")

class PaperMetadata(BaseModel):
    title: str
    authors: List[str] = []
    abstract: str = ""
    publication_year: Optional[int] = None
    journal: Optional[str] = None
    doi: Optional[str] = None
    citation_count: Optional[int] = None

class PaperUploadResponse(BaseModel):
    id: str
    title: str
    authors: List[str] = []
    abstract: str = ""
    file_name: Optional[str] = None
    source_url: Optional[str] = None
    created_at: datetime

class PaperDetailResponse(BaseModel):
    id: str
    user_id: Optional[str] = None
    title: str
    authors: List[str] = []
    abstract: str = ""
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    source_url: Optional[str] = None
    analysis: Optional[AIAnalysis] = None
    created_at: datetime

    class Config:
        from_attributes = True

class PaperListResponse(BaseModel):
    id: str
    title: str
    authors: List[str] = []
    file_name: Optional[str] = None
    created_at: datetime

class URLUploadRequest(BaseModel):
    url: str

class TextUploadRequest(BaseModel):
    title: str
    text: str
    authors: Optional[str] = None

class BookmarkCreate(BaseModel):
    paper_id: Optional[str] = None
    external_id: Optional[str] = None
    title: str
    authors: List[str] = []
    abstract: str = ""
    url: Optional[str] = None
    source: str = "custom"
    publication_year: Optional[int] = None

class BookmarkResponse(BaseModel):
    id: str
    user_id: str
    paper_id: Optional[str] = None
    external_id: Optional[str] = None
    title: str
    authors: List[str] = []
    abstract: str = ""
    url: Optional[str] = None
    source: str
    publication_year: Optional[int] = None
    created_at: datetime
