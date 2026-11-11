import unittest
from dataclasses import dataclass
from unittest.mock import patch

from ai.embeddings.openai_provider import OpenAIEmbeddingProvider


@dataclass
class FakeEmbedding:
    index: int
    embedding: list[float]


@dataclass
class FakeResponse:
    data: list[FakeEmbedding]


class FakeEmbeddingsEndpoint:
    def __init__(self, response: FakeResponse):
        self.response = response
        self.last_request = None

    def create(self, **kwargs):
        self.last_request = kwargs
        return self.response


class FakeClient:
    def __init__(self, response: FakeResponse):
        self.embeddings = FakeEmbeddingsEndpoint(response)


class OpenAIEmbeddingProviderTests(unittest.TestCase):
    def test_embeds_text_with_expected_official_sdk_request(self):
        client = FakeClient(FakeResponse([FakeEmbedding(0, [0.1, 0.2])]))
        provider = OpenAIEmbeddingProvider(
            client=client,
            model="text-embedding-3-small",
            dimensions=2,
        )

        embedding = provider.embed_text("  present perfect  ")

        self.assertEqual(embedding, (0.1, 0.2))
        self.assertEqual(
            client.embeddings.last_request,
            {
                "input": ["present perfect"],
                "model": "text-embedding-3-small",
                "encoding_format": "float",
                "dimensions": 2,
            },
        )

    def test_batch_response_is_returned_in_input_order(self):
        client = FakeClient(
            FakeResponse(
                [
                    FakeEmbedding(1, [0.0, 1.0]),
                    FakeEmbedding(0, [1.0, 0.0]),
                ]
            )
        )
        provider = OpenAIEmbeddingProvider(client, "text-embedding-3-small")

        embeddings = provider.embed_texts(["grammar", "vocabulary"])

        self.assertEqual(embeddings, [(1.0, 0.0), (0.0, 1.0)])

    def test_empty_input_or_invalid_configuration_is_rejected(self):
        client = FakeClient(FakeResponse([]))

        with self.assertRaises(ValueError):
            OpenAIEmbeddingProvider(client, "")
        with self.assertRaises(ValueError):
            OpenAIEmbeddingProvider(client, "model", dimensions=0)

        provider = OpenAIEmbeddingProvider(client, "model")
        with self.assertRaises(ValueError):
            provider.embed_text("   ")
        with self.assertRaises(ValueError):
            provider.embed_texts([])

    def test_malformed_provider_response_is_rejected(self):
        client = FakeClient(FakeResponse([FakeEmbedding(0, [float("nan")])]))
        provider = OpenAIEmbeddingProvider(client, "model")

        with self.assertRaises(ValueError):
            provider.embed_text("valid text")

        wrong_index = FakeClient(FakeResponse([FakeEmbedding(3, [1.0])]))
        with self.assertRaises(ValueError):
            OpenAIEmbeddingProvider(wrong_index, "model").embed_text("valid text")

    def test_invalid_environment_dimensions_are_rejected_before_sdk_use(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(ValueError, "OPENAI_EMBEDDING_MODEL"):
                OpenAIEmbeddingProvider.from_environment()

        with patch.dict(
            "os.environ",
            {
                "OPENAI_EMBEDDING_MODEL": "text-embedding-3-small",
                "OPENAI_EMBEDDING_DIMENSIONS": "not-a-number",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(ValueError, "número entero"):
                OpenAIEmbeddingProvider.from_environment()


if __name__ == "__main__":
    unittest.main()
