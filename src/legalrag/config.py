from dataclasses import asdict, dataclass
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Config:
    root: Path = ROOT
    embedding_model: str = "BAAI/bge-m3"
    llm_model: str = "Qwen/Qwen3-8B"
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    embedding_revision: str = "5617a9f61b028005a4858fdac845db406aefb181"
    llm_revision: str = "b968826d9c46dd6066d109eabc6255188de91218"
    reranker_revision: str = "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"
    device: str = "cuda"
    batch_size: int = 8
    reranker_batch_size: int = 6
    window_tokens: int = 512
    overlap_tokens: int = 64
    embedding_max_tokens: int = 1024
    top_k_retrieval: int = 50
    top_k_evidence: int = 10
    context_tokens: int = 5500
    max_input_tokens: int = 6500
    max_new_tokens: int = 700
    min_reranker_score: float = 0.25
    rrf_k: int = 60
    seed: int = 17
    hybrid: bool = False
    use_reranker: bool = True
    use_hyde: bool = True
    mc_thinking: bool = True
    mc_thinking_max_tokens: int = 768
    augment_max: int = 6
    augment_min_rerank: float = 0.15
    norm_hint: bool = False
    multi_query: bool = False
    multi_query_threshold: float = 0.4
    # Cerberus Mark 43: herramientas corregidas (SMLMV 2026, UVT, años, liquidación) y normalizador de citas.
    herramientas_v2: bool = False
    normalizador_citas: bool = False
    normalizador_directo: bool = False
    # Mark 44: cierre del thinking truncado, juicio de contexto suficiente y reformulador anclado en la evidencia.
    cerrar_pensamiento: bool = False
    suficiencia: bool = False
    umbral_suficiencia: float = 0.5
    reformulador_iterativo: bool = False
    # Mark 44: cerradas con reloj (thinking acotado por tiempo + letra por probabilidad + justificación corta)
    # y presupuesto de tiempo por pregunta (segundos, 0 = sin límite).
    mc_rapido: bool = False
    mc_reserva_s: float = 4.5
    mc_json_tokens: int = 150
    presupuesto_s: float = 0.0
    seguridad_s: float = 0.0  # tope de seguridad por generación (no decide nada en uso normal)
    bm25_sin_vacias: bool = False
    subconsultas_sin_pista: bool = False
    jerarquia_normativa: bool = False
    jerarquia_condicional: bool = False
    preferir_jurisprudencia: bool = False
    consulta_con_tema: bool = False
    tema_en_reranker: bool = False
    reservar_reformulador: bool = False
    umbral_reformulador: float = 0.5
    reservar_nombradas: bool = False
    encabezado_canonico: bool = False
    # Corpus reindexado (2-oct): jerarquía normativa en la recuperación (retrieval/kelsen.py).
    kelsen_boost: bool = False
    kelsen_diversificar: bool = False
    orden_juridico_libre: bool = False  # el orden de kelsen_diversificar, solo en texto libre
    kelsen_codigos: bool = False
    kelsen_doctrina: bool = False
    kelsen_horizontal: bool = False  # artículos derogados por entero ×0,5 (lex posterior)
    kelsen_especial: bool = False  # normas de la materia de la pregunta ×1,02 (lex specialis)
    jurisprudencia_reciente: bool = False  # precedente: sentencias C/SU/casación más recientes primero (lex posterior)
    mc_opciones: bool = False  # cerradas con evidencia débil: un pasaje que defina cada opción que nombra una figura
    umbral_opciones: float = 0.5
    abiertas_directas: bool = False
    area_en_prompt: bool = False
    area_en_conceptuales: bool = False  # área y tema solo en sub-tareas conceptuales (definición, elemento esencial…)
    semi_concisas: bool = False
    citar_propios_primero: bool = False
    propios_en_precedente: bool = False  # solo en sub-tareas de precedente / sentido del fallo
    agente_figuras: bool = False
    razonamiento_juridico: bool = False
    razonar_binarias: bool = False
    conocimiento_propio: bool = False
    enrutador: bool = False
    binarias_pensar_tokens: int = 512
    umbral_figuras: float = 0.5
    max_por_documento: int = 0  # 0 = sin tope de fragmentos por documento en la evidencia
    tokens_por_s: float = 40.0  # decodificación de Qwen3-8B bf16 en la 4090 (medido: 42-44)
    max_params: int = 9_000_000_000

    @property
    def prepared(self):
        return self.root / "data/processed/corpus_preparado"

    @property
    def data_dir(self):
        return self.root / "data"

    @property
    def index_dir(self):
        return self.root / "index"

    @property
    def reports(self):
        return self.root / "reports"

    @property
    def questions_file(self):
        return self.data_dir / "oficial/data/sample_50.jsonl"

    @property
    def schema_file(self):
        return self.data_dir / "oficial/schema/submission.schema.json"

    @property
    def output_file(self):
        return self.root / "submissions.jsonl"

    def serializable(self):
        return {k: str(v) if isinstance(v, Path) else v for k, v in asdict(self).items()}

    @classmethod
    def from_env(cls):
        return cls(root=Path(os.environ.get("LEGALRAG_ROOT", ROOT)).resolve())


CONFIG = Config.from_env()

# Opciones de cada mark (las mismas de `legalrag.cli run`); ver MARKS.md. Viven aquí, y no en `src/main.py`,
# para que la entrega (`src/main.py`) y la interfaz (`legalrag.cli serve`) respondan con la misma configuración:
# el §7 del enunciado exige que lo que el jurado regenere en vivo coincida con lo entregado.
MARK_42 = {"hybrid": True, "use_hyde": False, "mc_thinking": True, "multi_query": True}
MARKS = {
    42: MARK_42,
    43: {**MARK_42, "herramientas_v2": True, "normalizador_citas": True},
}
# Mark 44: cerradas en una sola generación (thinking hasta 1.536 tokens, letra por probabilidad en fp32,
# justificación corta), sin decisiones por reloj (determinista; 90 s solo como seguridad): 42,90 (13/15),
# 15,8 s de promedio (el enunciado pide ~22 s de promedio sobre las 992).
# Más los agentes de Cerberus: juez de contexto suficiente (Mark 4) y reformulador anclado en los pasajes
# (Mark 3, ITER-RETGEN): 44,47 (cerradas 14/15), 19,3 s de promedio.
MARKS[44] = {**MARKS[43], "mc_rapido": True, "mc_thinking_max_tokens": 1536, "seguridad_s": 90.0,
             "reranker_batch_size": 16, "suficiencia": True, "reformulador_iterativo": True,
             # Citas: encabezado canónico (66 normas con título descriptivo no eran citables) y 2 fragmentos de
             # cada norma nombrada en la pregunta (texto libre): 45,11, recall de citas 0,857, 18,9 s.
             "encabezado_canonico": True, "reservar_nombradas": True,
             # En preguntas de precedente o sentido del fallo (§4.2), la jurisprudencia respaldada se cita primero.
             # Con el arreglo de render (sentencias con año): 45,93, recall de citas 0,898, 19,0 s.
             "preferir_jurisprudencia": True}
# Mark 45: corpus reindexado del 2-oct (núcleo 22.247 documentos). Con el mismo Mark 44 dio 41,98; el puntaje del
# reranker ponderado por la jerarquía normativa (retrieval/kelsen.py) sube el techo de citas 0,898 → 0,939:
# 42,80, recall de citas 0,898, 19,8 s, 0 empeoras.
MARKS[45] = {**MARKS[44], "kelsen_boost": True}
# Mark 46: el normalizador de citas pide evaluar la opción con el año corregido («Ley 1564 de 2002» → 2012), salvo que
# otra opción ya cite esa norma con el año real (distractor deliberado): 44,36, cerradas 13/15, 19,6 s, 0 empeoras.
MARKS[46] = {**MARKS[45], "normalizador_directo": True}
# Mark 47: «pensar como abogado» en texto libre. La evidencia entra en orden jurídico (Constitución → leyes y códigos →
# decretos → jurisprudencia → doctrina; solo texto libre: en cerradas cambiaba la letra de la 647), el redactor razona
# tipo IRAC (norma de mayor jerarquía, jurisprudencia para interpretarla, ignorar pasajes ajenos) y los códigos expedidos
# por decreto (CST, Código de Comercio, Estatuto Tributario) pesan como ley en kelsen_boost.
# 44,36 (0 empeoras), RAGAS local 12,08 → 13,03, 19,9 s.
MARKS[47] = {**MARKS[46], "orden_juridico_libre": True, "razonamiento_juridico": True, "kelsen_codigos": True}
# Mark 48: ponderación horizontal (criterio cronológico, lex posterior: Ley 153 de 1887, arts. 2 y 3; Nino): un artículo
# derogado por entero pesa la mitad en el reranker y deja su cupo a la norma vigente. 44,36 (0 empeoras), RAGAS local
# 13,03 → 13,13, 19,7 s.
MARKS[48] = {**MARKS[47], "kelsen_horizontal": True}
# Mark 49: el criterio cronológico aplicado al precedente. En preguntas de precedente o sentido del fallo, las sentencias
# respaldadas que se agregan a la cita van de la más reciente a la más antigua, primero las de fuerza general (C, SU,
# casación) y después las de tutela y los autos. Solo cambia el orden de las citas agregadas, no la generación:
# 44,36 → 44,77 (+453, 0 empeoras), RAGAS igual (la referencia legal no va al juez), 0 s de costo.
MARKS[49] = {**MARKS[48], "jurisprudencia_reciente": True}
# Mark 50: semiabiertas concisas (2 a 4 oraciones; la primera responde exactamente lo preguntado, las demás solo el
# fundamento necesario). RAGAS mide F1 de enunciados frente a la referencia: cada enunciado de más es un falso positivo.
# Sobre el IRAC de Mark 47: 44,77 (0 empeoras), RAGAS local 13,13 → 13,87, 19,7 s. Solo cambia el prompt: no depende
# del índice.
MARKS[50] = {**MARKS[49], "semi_concisas": True}
MARK_ACTUAL = max(MARKS)

DATA_DIR = CONFIG.data_dir
INDEX_DIR = CONFIG.index_dir
OUTPUT_FILE = CONFIG.output_file
QUESTIONS_FILE = CONFIG.questions_file
EMBEDDING_MODEL = CONFIG.embedding_model
LLM_MODEL = CONFIG.llm_model
RERANKER_MODEL = CONFIG.reranker_model
TOP_K_RETRIEVAL = CONFIG.top_k_retrieval
TOP_K_RERANK = CONFIG.top_k_evidence
BATCH_SIZE = CONFIG.batch_size
DEVICE = CONFIG.device
