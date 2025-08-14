import json
import os
import re
from typing import List, Dict, Any
from django.core.management.base import BaseCommand
from django.conf import settings

class LegalDataPipeline:
    """
    Pipeline for processing legal documents and creating training datasets
    for LLM fine-tuning with Albanian legal texts.
    """
    
    def __init__(self, output_dir: str = "datasets"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def anonymize_text(self, text: str) -> str:
        """
        Anonymize sensitive information in legal texts.
        
        Args:
            text: Raw legal text
            
        Returns:
            Anonymized text
        """
        # Remove personal names (Albanian pattern)
        text = re.sub(r'\b[A-ZË][a-zë]+ [A-ZË][a-zë]+\b', '[EMËR]', text)
        
        # Remove addresses
        text = re.sub(r'\b(?:Rruga|Bulevardi|Lagja) [^\n,]+', '[ADRESË]', text)
        
        # Remove phone numbers
        text = re.sub(r'\+355\s?\d{8,9}|\b06\d{8}\b', '[TELEFON]', text)
        
        # Remove email addresses
        text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]', text)
        
        # Remove ID numbers (Albanian pattern)
        text = re.sub(r'\b[A-Z]\d{8}[A-Z]\b', '[ID]', text)
        
        # Remove dates in various formats
        text = re.sub(r'\b\d{1,2}[./]\d{1,2}[./]\d{4}\b', '[DATË]', text)
        
        # Remove monetary amounts
        text = re.sub(r'\b\d+[.,]?\d*\s?(?:lekë|euro|EUR|ALL)\b', '[SHUMË]', text)
        
        return text
    
    def extract_legal_qa_pairs(self, legal_text: str, source: str) -> List[Dict[str, str]]:
        """
        Extract question-answer pairs from legal documents.
        
        Args:
            legal_text: Processed legal text
            source: Source of the document
            
        Returns:
            List of Q&A pairs
        """
        pairs = []
        
        # Split by articles/sections
        articles = re.split(r'\n(?=Neni \d+)', legal_text)
        
        for article in articles:
            if not article.strip():
                continue
                
            # Extract article number and title
            article_match = re.match(r'Neni (\d+)\.?\s*-?\s*(.+?)(?:\n|$)', article)
            if not article_match:
                continue
                
            article_num = article_match.group(1)
            article_title = article_match.group(2).strip()
            article_content = article[article_match.end():].strip()
            
            # Generate different types of questions
            pairs.extend([
                {
                    "prompt": f"Cila dispozitë e {source} rregullon {article_title.lower()}?",
                    "completion": f"Neni {article_num} - {article_title}: {article_content[:200]}..."
                },
                {
                    "prompt": f"Si interpretohet Neni {article_num} i {source}?",
                    "completion": f"Neni {article_num} interpretohet si: {article_content}"
                },
                {
                    "prompt": f"Çfarë parashikon {source} për {article_title.lower()}?",
                    "completion": f"Sipas Nenit {article_num}: {article_content}"
                }
            ])
        
        return pairs
    
    def create_jsonl_dataset(self, qa_pairs: List[Dict[str, str]], filename: str) -> str:
        """
        Create JSONL dataset file for fine-tuning.
        
        Args:
            qa_pairs: List of question-answer pairs
            filename: Output filename
            
        Returns:
            Path to created file
        """
        output_path = os.path.join(self.output_dir, f"{filename}.jsonl")
        
        with open(output_path, 'w', encoding='utf-8') as f:
            for pair in qa_pairs:
                # Format for OpenAI fine-tuning
                training_example = {
                    "messages": [
                        {"role": "system", "content": "Ju jeni një asistent ligjor për Shqipërinë. Jepni përgjigje të sakta dhe të detajuara me referime në ligje."},
                        {"role": "user", "content": pair["prompt"]},
                        {"role": "assistant", "content": pair["completion"]}
                    ]
                }
                f.write(json.dumps(training_example, ensure_ascii=False) + '\n')
        
        return output_path
    
    def process_legal_document(self, file_path: str, source_name: str) -> List[Dict[str, str]]:
        """
        Process a legal document and extract training data.
        
        Args:
            file_path: Path to legal document
            source_name: Name of the legal source
            
        Returns:
            List of Q&A pairs
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Anonymize the content
            anonymized_content = self.anonymize_text(content)
            
            # Extract Q&A pairs
            qa_pairs = self.extract_legal_qa_pairs(anonymized_content, source_name)
            
            return qa_pairs
            
        except Exception as e:
            print(f"Error processing {file_path}: {str(e)}")
            return []
    
    def create_training_dataset(self, documents: List[Dict[str, str]]) -> str:
        """
        Create a complete training dataset from multiple legal documents.
        
        Args:
            documents: List of dicts with 'path' and 'source' keys
            
        Returns:
            Path to created dataset
        """
        all_pairs = []
        
        for doc in documents:
            pairs = self.process_legal_document(doc['path'], doc['source'])
            all_pairs.extend(pairs)
        
        # Split into train/test
        import random
        random.shuffle(all_pairs)
        
        split_point = int(0.9 * len(all_pairs))
        train_pairs = all_pairs[:split_point]
        test_pairs = all_pairs[split_point:]
        
        # Create datasets
        train_path = self.create_jsonl_dataset(train_pairs, "legal_train")
        test_path = self.create_jsonl_dataset(test_pairs, "legal_test")
        
        # Create metadata
        metadata = {
            "total_pairs": len(all_pairs),
            "train_pairs": len(train_pairs),
            "test_pairs": len(test_pairs),
            "sources": [doc['source'] for doc in documents],
            "created_at": str(timezone.now()),
            "version": "1.0"
        }
        
        metadata_path = os.path.join(self.output_dir, "metadata.json")
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        print(f"Dataset created successfully!")
        print(f"Training set: {train_path} ({len(train_pairs)} examples)")
        print(f"Test set: {test_path} ({len(test_pairs)} examples)")
        print(f"Metadata: {metadata_path}")
        
        return train_path

# Example usage and sample legal documents
SAMPLE_LEGAL_DOCUMENTS = [
    {
        "path": "sample_docs/kodi_penal.txt",
        "source": "Kodi Penal i Republikës së Shqipërisë"
    },
    {
        "path": "sample_docs/kodi_civil.txt", 
        "source": "Kodi Civil i Republikës së Shqipërisë"
    },
    {
        "path": "sample_docs/kodi_familjar.txt",
        "source": "Kodi i Familjes së Republikës së Shqipërisë"
    }
]

class Command(BaseCommand):
    """Django management command for data pipeline."""
    
    help = 'Process legal documents and create training datasets for LLM fine-tuning'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--documents-dir',
            type=str,
            default='legal_documents',
            help='Directory containing legal documents'
        )
        parser.add_argument(
            '--output-dir',
            type=str,
            default='datasets',
            help='Output directory for datasets'
        )
    
    def handle(self, *args, **options):
        pipeline = LegalDataPipeline(options['output_dir'])
        
        # Scan for legal documents
        documents_dir = options['documents_dir']
        if not os.path.exists(documents_dir):
            self.stdout.write(
                self.style.ERROR(f"Documents directory {documents_dir} does not exist")
            )
            return
        
        documents = []
        for filename in os.listdir(documents_dir):
            if filename.endswith('.txt'):
                documents.append({
                    'path': os.path.join(documents_dir, filename),
                    'source': filename.replace('.txt', '').replace('_', ' ').title()
                })
        
        if not documents:
            self.stdout.write(
                self.style.WARNING(f"No .txt files found in {documents_dir}")
            )
            return
        
        self.stdout.write(f"Processing {len(documents)} documents...")
        
        try:
            dataset_path = pipeline.create_training_dataset(documents)
            self.stdout.write(
                self.style.SUCCESS(f"Successfully created dataset: {dataset_path}")
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Error creating dataset: {str(e)}")
            )

if __name__ == "__main__":
    # Example usage
    pipeline = LegalDataPipeline()
    
    # Create sample dataset (you would replace this with actual legal documents)
    sample_text = """
    Neni 1 - Objekti i ligjit
    Ky ligj rregullon marrëdhëniet juridike në fushën e së drejtës civile.
    
    Neni 2 - Fushëveprimi
    Dispozitat e këtij ligji zbatohen për të gjitha marrëdhëniet civile.
    """
    
    qa_pairs = pipeline.extract_legal_qa_pairs(sample_text, "Kodi Civil")
    if qa_pairs:
        dataset_path = pipeline.create_jsonl_dataset(qa_pairs, "sample_legal_dataset")
        print(f"Sample dataset created: {dataset_path}")
