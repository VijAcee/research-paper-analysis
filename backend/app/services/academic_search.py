import urllib.parse
import xml.etree.ElementTree as ET
import requests
from typing import List, Dict, Any, Optional

from app.config import settings
from app.services.openai_service import get_openai_client

def search_semantic_scholar(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Searches Semantic Scholar API for papers."""
    results = []
    encoded_query = urllib.parse.quote(query)
    url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={encoded_query}&limit={limit}&fields=title,authors,year,journal,citationCount,abstract,url"
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            papers = data.get("data", [])
            for p in papers:
                authors = [a.get("name", "") for a in p.get("authors", []) if a.get("name")]
                journal_info = p.get("journal", {})
                journal_name = journal_info.get("name") if journal_info else None
                
                results.append({
                    "id": f"ss_{p.get('paperId')}",
                    "title": p.get("title", "Unknown Title"),
                    "authors": authors if authors else ["Authors Unspecified"],
                    "publication_year": p.get("year"),
                    "journal": journal_name or "Academic Publication",
                    "citation_count": p.get("citationCount", 0),
                    "abstract": p.get("abstract", "") or "",
                    "url": p.get("url", ""),
                    "source": "Semantic Scholar"
                })
    except Exception as e:
        print(f"Semantic Scholar API search failed: {e}")
        
    return results

def search_arxiv(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Searches arXiv API for papers."""
    results = []
    encoded_query = urllib.parse.quote(query)
    url = f"http://export.arxiv.org/api/query?search_query=all:{encoded_query}&max_results={limit}"
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            # Register namespaces
            ns = {'atom': 'http://www.w3.org/2005/Atom', 'arxiv': 'http://arxiv.org/schemas/atom'}
            
            for entry in root.findall('atom:entry', ns):
                title = entry.find('atom:title', ns)
                title_text = title.text.strip().replace('\n', ' ') if title is not None else "Unknown Title"
                
                # Extract authors
                authors = []
                for author in entry.findall('atom:author', ns):
                    name = author.find('atom:name', ns)
                    if name is not None:
                        authors.append(name.text.strip())
                        
                published = entry.find('atom:published', ns)
                year = None
                if published is not None and len(published.text) >= 4:
                    try:
                        year = int(published.text[:4])
                    except ValueError:
                        pass
                        
                summary = entry.find('atom:summary', ns)
                abstract = summary.text.strip().replace('\n', ' ') if summary is not None else ""
                
                id_url = entry.find('atom:id', ns)
                paper_url = id_url.text.strip() if id_url is not None else ""
                
                # Check for PDF links
                for link in entry.findall('atom:link', ns):
                    if link.attrib.get('title') == 'pdf':
                        paper_url = link.attrib.get('href', paper_url)
                        
                results.append({
                    "id": f"arxiv_{paper_url.split('/abs/')[-1]}",
                    "title": title_text,
                    "authors": authors if authors else ["Authors Unspecified"],
                    "publication_year": year,
                    "journal": "arXiv Preprints",
                    "citation_count": 0,
                    "abstract": abstract,
                    "url": paper_url,
                    "source": "arXiv"
                })
    except Exception as e:
        print(f"arXiv API search failed: {e}")
        
    return results

def search_related_papers(query: str, limit: int = 8) -> List[Dict[str, Any]]:
    """
    Searches both Semantic Scholar and arXiv, merging and returning the most relevant results.
    """
    # Clean the query slightly for better search results
    clean_query = query.strip()
    if len(clean_query) > 100:
        # Take first 10 words if query is a long sentence or abstract
        clean_query = " ".join(clean_query.split()[:10])
        
    ss_results = search_semantic_scholar(clean_query, limit=limit)
    arxiv_results = search_arxiv(clean_query, limit=limit)
    
    # Merge results, prioritizing Semantic Scholar but appending unique titles from arXiv
    merged_results = []
    seen_titles = set()
    
    for r in ss_results:
        norm_title = r["title"].lower().strip()
        if norm_title not in seen_titles:
            seen_titles.add(norm_title)
            merged_results.append(r)
            
    for r in arxiv_results:
        norm_title = r["title"].lower().strip()
        if norm_title not in seen_titles:
            seen_titles.add(norm_title)
            merged_results.append(r)
            
    # Calculate a simple mock relevance score based on query overlap
    query_words = set(clean_query.lower().split())
    for r in merged_results:
        title_words = set(r["title"].lower().split())
        overlap = len(query_words.intersection(title_words))
        score = min(98, 70 + (overlap * 5))
        r["relevance_score"] = score
        # Generate tags
        r["tags"] = [word.capitalize() for word in list(title_words.intersection(query_words)) if len(word) > 4][:3]
        if not r["tags"]:
            r["tags"] = ["Research", "Science"]
            
    # Sort by relevance score or citations
    merged_results.sort(key=lambda x: (x.get("relevance_score", 0), x.get("citation_count", 0)), reverse=True)
    return merged_results[:limit]

def summarize_external_paper(title: str, abstract: str) -> str:
    """
    Generates a rapid summary of an external paper based solely on its title and abstract.
    """
    if not abstract:
        return "No abstract available to generate a summary."
        
    client = get_openai_client()
    if not client:
        return f"**Quick Summary (Demo Mode)**:\nThis study explores methodologies related to the topic of **{title}**. The abstract outlines key concepts emphasizing performance optimization, deployment efficiency, and algorithmic refinements. Please configure your OpenAI API Key in the backend settings for automated detailed AI summaries."

    prompt = f"""
    You are a professional research AI. The user has discovered a paper online and wants a concise summary of it based only on the title and abstract.
    
    Title: {title}
    Abstract: {abstract}
    
    Write a structured summary containing:
    1. **Core Objective**: What are they trying to do?
    2. **Key Findings / Contributions**: What did they discover or build?
    3. **Significance**: Why does it matter to this domain?
    
    Keep it clear, concise (under 250 words), and format with Markdown.
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a concise academic research assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Failed to generate summary: {str(e)}"
