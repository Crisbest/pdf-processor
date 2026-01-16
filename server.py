from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
import fitz  # PyMuPDF
import re
import os
import uuid
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

app = FastAPI(title="PDF Processor API", version="1.0")

# CORS per permettere richieste dal browser
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cartelle di lavoro
UPLOAD_FOLDER = Path("uploads")
PROCESSED_FOLDER = Path("processed")
UPLOAD_FOLDER.mkdir(exist_ok=True)
PROCESSED_FOLDER.mkdir(exist_ok=True)

# Cache processi in memoria (in produzione usa Redis o database)
processes: Dict[str, Dict] = {}

# Configurazione traduzioni
TRANSLATIONS = {
    "Klamka okienna": "Maniglia finestra",
    "Biała": "Bianca",
    "Próg aluminiowy ciepły": "Soglia in alluminio a taglio termico",
    "Próg aluminiowy": "Soglia in alluminio",
    "czynne": "attiva",
    "bierne": "passiva",
    "stała": "fissa",
    "mikro": "micro",
    "NISKI PRÓG ALUM W BALKONIE": "SOGLIA BASSA IN ALLUMINIO NEL BALCONE",
    "Inny typ w zestawie": "Altro tipo nel set",
    "Kod ramy": "Codice telaio",
    "Kod skrzydła": "Codice anta",
    "Powierzchnia": "Superficie",
    "Obwód": "Perimetro",
    "Vista da interno": "Vista interna",
    "quantita": "quantità",
    "Unita' di produzione": "Unità di produzione",
    "Sommario": "Riepilogo",
    "Prodotto standard": "Prodotto standard",
    "In totale": "Totale",
    "Totale peso": "Peso totale",
    "Totale quantita' di telai": "Quantità totale telai"
}

REMOVE_TEXTS = ["Offerta n.", "Rif:", "Per:", "Offerta del giorno:", "PLN"]

PRICE_PATTERNS = [
    r"\b\d{1,3}([ .]\d{3})*(,\d{2})?\b",
    r"\bPLN\b",
    r"\b\d+%\b"
]

class PDFProcessor:
    def __init__(self, input_path: Path, output_path: Path, config: Dict):
        self.input_path = input_path
        self.output_path = output_path
        self.config = config
        self.stats = {
            "translations": 0,
            "prices_removed": 0,
            "pages": 0,
            "processing_time": 0
        }
        
    def process(self):
        start_time = datetime.now()
        
        doc = fitz.open(self.input_path)
        self.stats["pages"] = len(doc)
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            
            # 1. Rimuovi intestazione (prime 100 punti dall'alto)
            if self.config.get("remove_header", True):
                header_rect = fitz.Rect(0, 0, page.rect.width, 100)
                page.add_redact_annot(header_rect, fill=(1, 1, 1))
            
            # 2. Cerca e sostituisci testo
            if self.config.get("translate", True):
                for pl_text, it_text in TRANSLATIONS.items():
                    text_instances = page.search_for(pl_text)
                    for inst in text_instances:
                        page.add_redact_annot(inst, fill=(1, 1, 1))
                        # Dopo redaction, potremmo reinserire il testo tradotto
                        # Ma per semplicità qui redigiamo e basta
            
            # 3. Rimuovi prezzi
            if self.config.get("remove_prices", True):
                # Rimuovi tabelle prezzi (cerca pattern)
                price_keywords = ["Prezzi netto", "Prezzo", "Sconto", "Valore", "IVA", "lordo", "netto"]
                for keyword in price_keywords:
                    text_instances = page.search_for(keyword)
                    for inst in text_instances:
                        # Estendi area per catturare tutta la riga
                        expanded_rect = fitz.Rect(inst.x0 - 10, inst.y0, inst.x1 + 200, inst.y1 + 20)
                        page.add_redact_annot(expanded_rect, fill=(1, 1, 1))
                        self.stats["prices_removed"] += 1
            
            # 4. Rimuovi RIF e PER
            if self.config.get("remove_ref", True):
                for text in ["Rif:", "RIF:", "Per:"]:
                    text_instances = page.search_for(text)
                    for inst in text_instances:
                        expanded_rect = fitz.Rect(inst.x0 - 5, inst.y0, inst.x1 + 150, inst.y1 + 5)
                        page.add_redact_annot(expanded_rect, fill=(1, 1, 1))
            
            # Applica tutte le redazioni
            page.apply_redactions()
            
            # 5. Inserisci testo tradotto (opzionale - versione avanzata)
            # Qui potremmo reinserire il testo tradotto nelle posizioni originali
        
        # Salva documento
        doc.save(self.output_path, deflate=True, garbage=4)
        doc.close()
        
        # Calcola statistiche
        end_time = datetime.now()
        self.stats["processing_time"] = (end_time - start_time).total_seconds()
        self.stats["output_size"] = os.path.getsize(self.output_path) / 1024
        
        return self.stats

@app.get("/")
async def root():
    return {"message": "PDF Processor API", "status": "online"}

@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.post("/upload")
async def upload_pdf(
    pdf: UploadFile = File(...),
    config: Optional[str] = None
):
    try:
        # Genera ID processo
        process_id = str(uuid.uuid4())
        
        # Salva file
        input_path = UPLOAD_FOLDER / f"{process_id}_input.pdf"
        with open(input_path, "wb") as f:
            shutil.copyfileobj(pdf.file, f)
        
        # Configurazione
        config_dict = json.loads(config) if config else {
            "translate": True,
            "remove_prices": True,
            "remove_header": True,
            "remove_ref": True,
            "preserve_layout": True
        }
        
        # Inizializza processo
        processes[process_id] = {
            "status": "processing",
            "message": "Inizio elaborazione",
            "progress": 10,
            "config": config_dict,
            "input_file": str(input_path),
            "output_file": None,
            "stats": None,
            "created_at": datetime.now().isoformat()
        }
        
        # Elabora in background
        output_path = PROCESSED_FOLDER / f"{process_id}_output.pdf"
        processor = PDFProcessor(input_path, output_path, config_dict)
        stats = processor.process()
        
        # Aggiorna processo
        processes[process_id].update({
            "status": "completed",
            "message": "Elaborazione completata",
            "progress": 100,
            "output_file": str(output_path),
            "stats": stats
        })
        
        return JSONResponse({
            "process_id": process_id,
            "status": "processing_started",
            "message": "PDF caricato e in elaborazione"
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status/{process_id}")
async def get_status(process_id: str):
    if process_id not in processes:
        raise HTTPException(status_code=404, detail="Processo non trovato")
    
    process = processes[process_id]
    return JSONResponse(process)

@app.get("/download/{process_id}")
async def download_pdf(process_id: str):
    if process_id not in processes:
        raise HTTPException(status_code=404, detail="Processo non trovato")
    
    process = processes[process_id]
    if process["status"] != "completed" or not process["output_file"]:
        raise HTTPException(status_code=400, detail="PDF non ancora pronto")
    
    return FileResponse(
        process["output_file"],
        filename=f"PDF_MODIFICATO_{process_id}.pdf",
        media_type="application/pdf"
    )

@app.get("/list-processes")
async def list_processes():
    return {
        "total": len(processes),
        "processes": list(processes.keys())
    }

@app.delete("/cleanup")
async def cleanup():
    """Pulisci file temporanei"""
    try:
        # Rimuovi file più vecchi di 1 ora
        import time
        current_time = time.time()
        
        for folder in [UPLOAD_FOLDER, PROCESSED_FOLDER]:
            for file in folder.glob("*"):
                if os.path.getctime(file) < current_time - 3600:  # 1 ora
                    os.remove(file)
        
        # Pulisci processi vecchi
        global processes
        processes = {pid: data for pid, data in processes.items() 
                    if datetime.fromisoformat(data["created_at"]) > datetime.now().replace(hour=-1)}
        
        return {"message": "Cleanup completato", "remaining_processes": len(processes)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
