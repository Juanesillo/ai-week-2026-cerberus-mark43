import argparse
from dataclasses import replace
from pathlib import Path
from legalrag.config import CONFIG, MARKS, MARK_ACTUAL


def main():
    from legalrag.silencio import silenciar
    silenciar()
    parser = argparse.ArgumentParser(description="Preguntas jurídicas con corpus colombiano")
    parser.add_argument("--root", type=Path, default=CONFIG.root)
    sub = parser.add_subparsers(dest="command", required=True)
    audit = sub.add_parser("audit")
    audit.add_argument("--questions", type=Path)
    audit.add_argument("--coverage", action="store_true")
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--replace", action="store_true")
    sub.add_parser("package-raw")
    sub.add_parser("profile")
    sub.add_parser("finalize")
    index = sub.add_parser("index")
    index.add_argument("--replace", action="store_true")
    index.add_argument("--batch-size", type=int, default=CONFIG.batch_size)
    run = sub.add_parser("run")
    run.add_argument("--questions", type=Path, required=True)
    run.add_argument("--output", type=Path)
    run.add_argument("--resume", action="store_true")
    run.add_argument("--expected-count", type=int)
    retrieval = run.add_mutually_exclusive_group()
    retrieval.add_argument("--dense-only", action="store_true")
    retrieval.add_argument("--hybrid", action="store_true")
    run.add_argument("--no-reranker", action="store_true")
    run.add_argument("--no-hyde", action="store_true")
    run.add_argument("--mc-thinking", action="store_true",
                     help="activa el modo 'thinking' de Qwen3 solo para preguntas cerradas")
    run.add_argument("--multi-query", action="store_true",
                     help="descompone la pregunta en sub-consultas cuando el retrieval es debil")
    run.add_argument("--herramientas-v2", action="store_true",
                     help="Mark 43: SMLMV 2026 correcto, UVT, dos años si la pregunta no trae año y plazos de "
                          "liquidacion solo si se habla de liquidar un contrato")
    run.add_argument("--normalizador", action="store_true",
                     help="Mark 43: avisa si la pregunta u opcion cita una ley con el ano equivocado")
    run.add_argument("--cerrar-pensamiento", action="store_true",
                     help="Mark 44: si el thinking de una cerrada se queda sin presupuesto, cierra </think> y "
                          "continua desde ese razonamiento en vez de regenerar sin thinking")
    run.add_argument("--suficiencia", action="store_true",
                     help="Mark 44: el decoder juzga si los 5 primeros pasajes bastan; si no, segunda busqueda")
    run.add_argument("--umbral-suficiencia", type=float, default=CONFIG.umbral_suficiencia,
                     help="P(Si) minima para dar el contexto por suficiente")
    run.add_argument("--reformulador-iterativo", action="store_true",
                     help="Mark 44: la segunda busqueda usa una respuesta breve escrita con los primeros pasajes")
    run.add_argument("--mc-rapido", action="store_true",
                     help="Mark 44: cerradas con thinking acotado por reloj, letra por probabilidad y justificacion corta")
    run.add_argument("--presupuesto", type=float, default=0.0,
                     help="Mark 44: segundos maximos por pregunta (0 = sin limite)")
    run.add_argument("--bm25-sin-vacias", action="store_true",
                     help="Mark 44: BM25 sin palabras vacias del espanol (consulta mas corta y rapida)")
    run.add_argument("--mc-pensar-tokens", type=int, default=CONFIG.mc_thinking_max_tokens,
                     help="tokens maximos de thinking en cerradas (el presupuesto determinista)")
    run.add_argument("--reranker-lote", type=int, default=CONFIG.reranker_batch_size)
    run.add_argument("--subconsultas-sin-pista", action="store_true",
                     help="Mark 44: las sub-consultas de multi_query sin la pista de area, en paralelo (mas rapido)")
    run.add_argument("--jerarquia", action="store_true",
                     help="Mark 44: regla de ponderacion por la jerarquia normativa colombiana (piramide de Kelsen)")
    run.add_argument("--reservar-nombradas", action="store_true",
                     help="Mark 44: en texto libre, 2 fragmentos de cada norma nombrada en la pregunta al frente")
    run.add_argument("--encabezado-canonico", action="store_true",
                     help="Mark 44: agrega 'Ley N de AAAA' al encabezado cuando su nombre descriptivo no es citable")
    run.add_argument("--seguridad", type=float, default=0.0,
                     help="Mark 44: segundos de seguridad por pregunta (solo corta generaciones desbocadas)")
    run.add_argument("--normalizador-directo", action="store_true",
                     help="Mark 44: la nota del normalizador pide evaluar la opcion con el ano corregido")
    run.add_argument("--jerarquia-condicional", action="store_true",
                     help="Mark 44: la regla de jerarquia solo en preguntas de jerarquia o conflicto normativo")
    run.add_argument("--preferir-jurisprudencia", action="store_true",
                     help="Mark 44: en preguntas de precedente, la jurisprudencia respaldada se agrega primero")
    run.add_argument("--consulta-con-tema", action="store_true",
                     help="Mark 44: el campo tema del banco se agrega a la consulta de busqueda")
    run.add_argument("--tema-en-reranker", action="store_true",
                     help="Mark 44: el tema tambien entra en la consulta del reranker")
    run.add_argument("--reservar-reformulador", action="store_true",
                     help="Mark 44: normas nombradas por el reformulador, si el reranker las confirma (texto libre)")
    run.add_argument("--kelsen-boost", action="store_true",
                     help="corpus 2-oct: el puntaje del reranker se pondera por la jerarquia normativa")
    run.add_argument("--kelsen-diversificar", action="store_true",
                     help="corpus 2-oct: solo las fuentes formales cuentan como estatuto, ordenadas por jerarquia")
    run.add_argument("--abiertas-directas", action="store_true",
                     help="abiertas: 1-3 normas en el marco y el analisis empieza con la respuesta al caso")
    run.add_argument("--area-en-prompt", action="store_true",
                     help="texto libre: el area y el tema del banco entran al prompt del generador")
    run.add_argument("--max-por-documento", type=int, default=0,
                     help="tope de fragmentos de un mismo documento entre los pasajes de evidencia (0 = sin tope)")
    run.add_argument("--semi-concisas", action="store_true",
                     help="semiabiertas: 2-4 oraciones, la respuesta directa primero y nada que no se pida")
    run.add_argument("--citar-propios-primero", action="store_true",
                     help="al agregar citas, primero las normas que son los pasajes y luego las que solo mencionan")
    run.add_argument("--agente-figuras", action="store_true",
                     help="Cerberus: el decoder nombra la figura del caso y el corpus dice que estatuto la regula")
    run.add_argument("--razonamiento-juridico", action="store_true",
                     help="texto libre: razonar como abogado (norma de mayor jerarquia, ignorar fragmentos ajenos)")
    run.add_argument("--razonar-binarias", action="store_true",
                     help="texto libre: el decoder razona (hasta 512 tokens) solo si la respuesta es si/no o verdadero/falso")
    run.add_argument("--kelsen-codigos", action="store_true",
                     help="kelsen_boost: codigos, estatutos y decretos-ley pesan como ley")
    run.add_argument("--kelsen-doctrina", action="store_true",
                     help="kelsen_boost: la jurisprudencia por encima de conceptos, oficios y circulares")
    run.add_argument("--conocimiento-propio", action="store_true",
                     help="texto libre: evidencia primero; si no responde, el conocimiento juridico del modelo")
    run.add_argument("--enrutador", action="store_true",
                     help="Cerberus: cada pregunta de texto libre va a los especialistas de su sub-tarea")
    run.add_argument("--propios-en-precedente", action="store_true",
                     help="en preguntas de precedente, citar primero las sentencias recuperadas que las solo mencionadas")
    run.add_argument("--orden-juridico-libre", action="store_true",
                     help="texto libre: evidencia en orden juridico (Constitucion, leyes, decretos, jurisprudencia, doctrina)")
    run.add_argument("--area-en-conceptuales", action="store_true",
                     help="texto libre: area y tema del banco en el prompt solo en sub-tareas conceptuales")
    run.add_argument("--kelsen-horizontal", action="store_true",
                     help="kelsen_boost: los articulos derogados por entero pesan la mitad (lex posterior)")
    run.add_argument("--kelsen-especial", action="store_true",
                     help="kelsen_boost: las normas de la materia de la pregunta pesan x1,02 (lex specialis)")
    run.add_argument("--jurisprudencia-reciente", action="store_true",
                     help="precedente: las sentencias C/SU/casacion mas recientes se citan primero (lex posterior)")
    run.add_argument("--mc-opciones", action="store_true",
                     help="cerradas con evidencia debil: un pasaje que defina cada opcion que nombra una figura juridica")
    run.add_argument("--augment-max", type=int, default=CONFIG.augment_max,
                     help="maximo de normas respaldadas que se agregan a la respuesta")
    run.add_argument("--threshold", type=float, default=CONFIG.min_reranker_score)
    evaluation = sub.add_parser("evaluate")
    evaluation.add_argument("--predictions", type=Path, required=True)
    evaluation.add_argument("--gold", type=Path)
    evaluation.add_argument("--official", action="store_true")
    evaluation.add_argument("--ragas", action="store_true")
    serve = sub.add_parser("serve")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--mark", type=int, default=MARK_ACTUAL, choices=sorted(MARKS),
                       help="configuración con la que responde la interfaz; por defecto la de la entrega")
    args = parser.parse_args()
    config = replace(CONFIG, root=args.root.resolve())
    if args.command == "profile":
        from legalrag.ingestion.profile import profile
        profile(config)
    elif args.command == "prepare":
        from legalrag.ingestion.prepare_raw import prepare_raw
        prepare_raw(config, replace=args.replace)
    elif args.command == "package-raw":
        from legalrag.ingestion.package_raw import package_raw
        package_raw(config)
    elif args.command == "audit":
        from legalrag.ingestion.gap_analysis import audit
        audit(config)
        if args.coverage:
            from legalrag.ingestion.coverage_audit import coverage_audit
            coverage_audit(config, args.questions or config.questions_file)
    elif args.command == "finalize":
        from legalrag.ingestion.finalize import finalize
        finalize(config)
    elif args.command == "index":
        if args.batch_size < 1:
            parser.error("--batch-size debe ser positivo")
        from legalrag.indexing.build_index import build_index
        build_index(replace(config, batch_size=args.batch_size), replace=args.replace)
    elif args.command == "run":
        if not 0 <= args.threshold <= 1:
            parser.error("--threshold debe estar entre 0 y 1")
        from legalrag.pipeline import run
        config = replace(config, hybrid=args.hybrid, use_reranker=not args.no_reranker,
                         use_hyde=not args.no_hyde, min_reranker_score=args.threshold,
                         mc_thinking=args.mc_thinking, augment_max=args.augment_max,
                         multi_query=args.multi_query, herramientas_v2=args.herramientas_v2,
                         normalizador_citas=args.normalizador,
                         cerrar_pensamiento=args.cerrar_pensamiento, suficiencia=args.suficiencia,
                         umbral_suficiencia=args.umbral_suficiencia,
                         reformulador_iterativo=args.reformulador_iterativo,
                         mc_rapido=args.mc_rapido, presupuesto_s=args.presupuesto,
                         bm25_sin_vacias=args.bm25_sin_vacias,
                         mc_thinking_max_tokens=args.mc_pensar_tokens, reranker_batch_size=args.reranker_lote,
                         subconsultas_sin_pista=args.subconsultas_sin_pista,
                         jerarquia_normativa=args.jerarquia,
                         reservar_nombradas=args.reservar_nombradas,
                         encabezado_canonico=args.encabezado_canonico,
                         seguridad_s=args.seguridad,
                         normalizador_directo=args.normalizador_directo,
                         jerarquia_condicional=args.jerarquia_condicional,
                         preferir_jurisprudencia=args.preferir_jurisprudencia,
                         consulta_con_tema=args.consulta_con_tema, tema_en_reranker=args.tema_en_reranker,
                         reservar_reformulador=args.reservar_reformulador,
                         kelsen_boost=args.kelsen_boost, kelsen_diversificar=args.kelsen_diversificar,
                         abiertas_directas=args.abiertas_directas,
                         area_en_prompt=args.area_en_prompt,
                         max_por_documento=args.max_por_documento,
                         semi_concisas=args.semi_concisas,
                         citar_propios_primero=args.citar_propios_primero,
                         agente_figuras=args.agente_figuras,
                         razonamiento_juridico=args.razonamiento_juridico,
                         razonar_binarias=args.razonar_binarias,
                         kelsen_codigos=args.kelsen_codigos, kelsen_doctrina=args.kelsen_doctrina,
                         conocimiento_propio=args.conocimiento_propio,
                         enrutador=args.enrutador,
                         propios_en_precedente=args.propios_en_precedente,
                         orden_juridico_libre=args.orden_juridico_libre,
                         area_en_conceptuales=args.area_en_conceptuales,
                         kelsen_horizontal=args.kelsen_horizontal,
                         kelsen_especial=args.kelsen_especial,
                         jurisprudencia_reciente=args.jurisprudencia_reciente,
                         mc_opciones=args.mc_opciones)
        run(config, args.questions, args.output or config.output_file, args.resume, args.expected_count)
    elif args.command == "evaluate":
        from legalrag.evaluation.evaluate import evaluate
        evaluate(config, args.predictions, args.gold, args.official, args.ragas)
    elif args.command == "serve":
        # La interfaz responde con la misma configuración que generó la entrega (§7: lo que el jurado
        # regenere en vivo debe coincidir con lo entregado). Sin esto servía con los valores por defecto.
        from legalrag.server import serve
        serve(replace(config, **MARKS[args.mark]), args.port)


if __name__ == "__main__":
    main()
