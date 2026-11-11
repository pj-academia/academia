# Embeddings con OpenAI

`openai_provider.py` encapsula la llamada al cliente oficial de OpenAI y entrega vectores a la lógica de memoria. El adaptador:

- admite un texto o un lote;
- rechaza entradas vacías y respuestas mal formadas;
- conserva el orden del lote mediante el índice devuelto por la API;
- permite configurar el modelo y, opcionalmente, las dimensiones;
- no almacena ni registra la API key.

La implementación sigue la [documentación oficial de embeddings de OpenAI](https://developers.openai.com/api/docs/guides/embeddings). Las pruebas usan un cliente simulado y no realizan llamadas externas ni consumen saldo.

Configuración prevista en `.env`:

```dotenv
OPENAI_API_KEY=
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_EMBEDDING_DIMENSIONS=
```

La dependencia oficial `openai` se añadirá al entorno del backend cuando Peio prepare su empaquetado. Hasta entonces, las pruebas de este módulo funcionan sin instalarla.
