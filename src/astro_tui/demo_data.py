"""Mock data factory for API-key-free showcase demos.

All functions return deterministic data so demos are reproducible.
"""

from __future__ import annotations

import hashlib
import math
import struct
from typing import Any

from astro_context import (
    ContextItem,
    DenseRetriever,
    EvaluationDataset,
    EvaluationSample,
    InMemoryContextStore,
    InMemoryVectorStore,
    SourceType,
    SparseRetriever,
)

# ---------------------------------------------------------------------------
# Sample documents (astronomy themed)
# ---------------------------------------------------------------------------

_DOCUMENTS: list[dict[str, str]] = [
    {
        "id": "doc-001",
        "title": "The Sun",
        "content": (
            "The Sun is the star at the center of our Solar System. It is a nearly perfect "
            "sphere of hot plasma, heated to incandescence by nuclear fusion reactions in its "
            "core. The Sun radiates energy mainly as visible light, ultraviolet, and infrared "
            "radiation, and is the most important source of energy for life on Earth."
        ),
    },
    {
        "id": "doc-002",
        "title": "Mercury",
        "content": (
            "Mercury is the smallest planet in the Solar System and the closest to the Sun. "
            "Its orbit around the Sun takes 87.97 Earth days, the shortest of all the Sun's "
            "planets. It has no atmosphere to retain heat, so temperatures vary drastically "
            "between day and night."
        ),
    },
    {
        "id": "doc-003",
        "title": "Venus",
        "content": (
            "Venus is the second planet from the Sun. It has the densest atmosphere of all "
            "terrestrial planets, consisting mostly of carbon dioxide with a thick sulfuric "
            "acid cloud layer. The surface temperature reaches about 467 degrees Celsius, "
            "making it the hottest planet in our Solar System."
        ),
    },
    {
        "id": "doc-004",
        "title": "Earth",
        "content": (
            "Earth is the third planet from the Sun and the only astronomical object known to "
            "harbor life. About 71 percent of Earth's surface is covered with water, mostly by "
            "oceans. Earth's atmosphere consists primarily of nitrogen and oxygen. The planet's "
            "magnetic field deflects most of the solar wind."
        ),
    },
    {
        "id": "doc-005",
        "title": "Mars",
        "content": (
            "Mars is the fourth planet from the Sun and the second-smallest planet in the Solar "
            "System. Mars is often called the Red Planet because of the iron oxide on its "
            "surface. It has two small moons, Phobos and Deimos. Mars has a thin atmosphere "
            "composed primarily of carbon dioxide."
        ),
    },
    {
        "id": "doc-006",
        "title": "Jupiter",
        "content": (
            "Jupiter is the fifth planet from the Sun and the largest in the Solar System. It "
            "is a gas giant with a mass more than two and a half times that of all the other "
            "planets combined. Jupiter's Great Red Spot is a giant storm that has been observed "
            "since at least 1831."
        ),
    },
    {
        "id": "doc-007",
        "title": "Saturn",
        "content": (
            "Saturn is the sixth planet from the Sun and the second-largest in the Solar System. "
            "It is best known for its prominent ring system, which is composed mostly of ice "
            "particles with a smaller amount of rocky debris and dust. Saturn has at least 146 "
            "known moons."
        ),
    },
    {
        "id": "doc-008",
        "title": "Black Holes",
        "content": (
            "A black hole is a region of spacetime where gravity is so strong that nothing, not "
            "even light, can escape. The theory of general relativity predicts that a sufficiently "
            "compact mass can deform spacetime to form a black hole. The boundary beyond which "
            "nothing can escape is called the event horizon."
        ),
    },
    {
        "id": "doc-009",
        "title": "Neutron Stars",
        "content": (
            "A neutron star is the collapsed core of a massive supergiant star. Neutron stars "
            "are the densest known objects in the universe, with a mass about 1.4 times that of "
            "the Sun packed into a sphere only about 20 kilometers in diameter. They rotate "
            "extremely rapidly and have intense magnetic fields."
        ),
    },
    {
        "id": "doc-010",
        "title": "The Milky Way",
        "content": (
            "The Milky Way is the galaxy that includes the Solar System. It is a barred spiral "
            "galaxy with an estimated 100 to 400 billion stars and at least that many planets. "
            "The Milky Way is about 100,000 light-years in diameter and the Sun is located about "
            "26,000 light-years from the galactic center."
        ),
    },
    {
        "id": "doc-011",
        "title": "Hubble Space Telescope",
        "content": (
            "The Hubble Space Telescope is a space telescope launched into low Earth orbit in "
            "1990. It remains one of the largest and most versatile astronomical instruments. "
            "Hubble has made over 1.5 million observations and helped determine the rate of "
            "expansion of the universe."
        ),
    },
    {
        "id": "doc-012",
        "title": "James Webb Space Telescope",
        "content": (
            "The James Webb Space Telescope is an infrared space observatory launched in December "
            "2021. It is designed to observe the most distant events and objects in the universe, "
            "such as the formation of the first galaxies. JWST operates at the second Lagrange "
            "point, about 1.5 million kilometers from Earth."
        ),
    },
    {
        "id": "doc-013",
        "title": "Exoplanets",
        "content": (
            "An exoplanet is a planet outside the Solar System. The first confirmation of an "
            "exoplanet orbiting a sun-like star was made in 1995. As of 2024, over 5,500 "
            "exoplanets have been confirmed. Detection methods include the radial velocity "
            "method and the transit method."
        ),
    },
    {
        "id": "doc-014",
        "title": "Dark Matter",
        "content": (
            "Dark matter is a hypothetical form of matter that does not interact with the "
            "electromagnetic field. It accounts for approximately 27 percent of the mass-energy "
            "of the universe. Evidence for dark matter comes from gravitational effects that "
            "cannot be explained by accepted theories of gravity unless more matter is present."
        ),
    },
    {
        "id": "doc-015",
        "title": "Dark Energy",
        "content": (
            "Dark energy is a hypothetical form of energy that permeates all of space and "
            "accelerates the expansion of the universe. It accounts for about 68 percent of "
            "the total energy in the observable universe. The nature of dark energy remains "
            "one of the greatest mysteries in physics."
        ),
    },
    {
        "id": "doc-016",
        "title": "The Big Bang",
        "content": (
            "The Big Bang theory is the prevailing cosmological description of the development "
            "of the universe. According to this theory, the universe expanded from a very high "
            "density and temperature state approximately 13.8 billion years ago. The cosmic "
            "microwave background radiation is the remnant heat from the early universe."
        ),
    },
    {
        "id": "doc-017",
        "title": "Asteroids",
        "content": (
            "Asteroids are minor planets of the inner Solar System. Most known asteroids orbit "
            "within the asteroid belt between Mars and Jupiter. The total mass of all asteroids "
            "combined is less than that of Earth's Moon. The largest asteroid is Ceres, which "
            "is also classified as a dwarf planet."
        ),
    },
    {
        "id": "doc-018",
        "title": "Comets",
        "content": (
            "A comet is an icy small Solar System body that, when passing close to the Sun, "
            "warms and begins to release gases, producing a visible atmosphere called a coma "
            "and sometimes a tail. Comets have orbital periods ranging from a few years to "
            "potentially millions of years."
        ),
    },
    {
        "id": "doc-019",
        "title": "Space Exploration",
        "content": (
            "Space exploration is the use of astronomy and space technology to explore outer "
            "space. The first human spaceflight was Vostok 1 in 1961. The Apollo 11 mission "
            "in 1969 was the first to land humans on the Moon. Current exploration includes "
            "Mars rovers, the International Space Station, and commercial spaceflight."
        ),
    },
    {
        "id": "doc-020",
        "title": "Gravitational Waves",
        "content": (
            "Gravitational waves are disturbances in the curvature of spacetime generated by "
            "accelerated masses that propagate as waves at the speed of light. They were first "
            "directly detected by LIGO in September 2015 from a pair of merging black holes. "
            "This discovery confirmed a major prediction of general relativity."
        ),
    },
]


def sample_documents() -> list[dict[str, str]]:
    """Return 20 sample documents about astronomy."""
    return list(_DOCUMENTS)


def sample_code() -> str:
    """Return a Python source file for CodeChunker demo."""
    return '''"""Example module for code chunking demonstration."""

import math
from dataclasses import dataclass


@dataclass
class Vector:
    """A 2D vector."""
    x: float
    y: float

    def magnitude(self) -> float:
        """Return the magnitude of the vector."""
        return math.sqrt(self.x ** 2 + self.y ** 2)

    def normalize(self) -> "Vector":
        """Return a unit vector in the same direction."""
        mag = self.magnitude()
        if mag == 0:
            return Vector(0, 0)
        return Vector(self.x / mag, self.y / mag)

    def dot(self, other: "Vector") -> float:
        """Return the dot product with another vector."""
        return self.x * other.x + self.y * other.y


def distance(a: Vector, b: Vector) -> float:
    """Calculate the Euclidean distance between two vectors."""
    dx = a.x - b.x
    dy = a.y - b.y
    return math.sqrt(dx * dx + dy * dy)


class Particle:
    """A simple particle with position and velocity."""

    def __init__(self, position: Vector, velocity: Vector, mass: float = 1.0):
        self.position = position
        self.velocity = velocity
        self.mass = mass

    def update(self, dt: float) -> None:
        """Update position based on velocity and time step."""
        self.position = Vector(
            self.position.x + self.velocity.x * dt,
            self.position.y + self.velocity.y * dt,
        )

    def kinetic_energy(self) -> float:
        """Calculate the kinetic energy of the particle."""
        v = self.velocity.magnitude()
        return 0.5 * self.mass * v * v


def simulate(particles: list[Particle], steps: int, dt: float = 0.01) -> list[list[Vector]]:
    """Run a simple particle simulation and return trajectories."""
    trajectories: list[list[Vector]] = [[] for _ in particles]
    for _ in range(steps):
        for i, p in enumerate(particles):
            trajectories[i].append(Vector(p.position.x, p.position.y))
            p.update(dt)
    return trajectories
'''


def sample_markdown() -> str:
    """Return a markdown article with tables and headers."""
    return """# Solar System Overview

The Solar System formed 4.6 billion years ago from the gravitational collapse
of a giant interstellar molecular cloud.

## Inner Planets

The inner planets are small and rocky.

| Planet  | Distance (AU) | Diameter (km) | Moons |
|---------|--------------|----------------|-------|
| Mercury | 0.39         | 4,879          | 0     |
| Venus   | 0.72         | 12,104         | 0     |
| Earth   | 1.00         | 12,742         | 1     |
| Mars    | 1.52         | 6,779          | 2     |

## Outer Planets

The outer planets are gas and ice giants.

| Planet  | Distance (AU) | Diameter (km) | Moons |
|---------|--------------|----------------|-------|
| Jupiter | 5.20         | 139,820        | 95    |
| Saturn  | 9.54         | 116,460        | 146   |
| Uranus  | 19.19        | 50,724         | 28    |
| Neptune | 30.07        | 49,244         | 16    |

## Notable Features

- **The Sun** contains 99.86% of the Solar System's mass
- **Jupiter's Great Red Spot** is larger than Earth
- **Saturn's rings** are mostly ice particles
- **Mars** has the tallest volcano: Olympus Mons (21.9 km)
"""


def sample_html() -> str:
    """Return an HTML page for HTMLParser demo."""
    return """<!DOCTYPE html>
<html>
<head><title>Astronomy Facts</title></head>
<body>
<h1>Astronomy Facts</h1>
<p>The universe is approximately 13.8 billion years old.</p>

<h2>Distances</h2>
<table border="1">
<tr><th>Object</th><th>Distance from Earth</th></tr>
<tr><td>Moon</td><td>384,400 km</td></tr>
<tr><td>Sun</td><td>149.6 million km</td></tr>
<tr><td>Proxima Centauri</td><td>4.24 light-years</td></tr>
</table>

<h2>Key Discoveries</h2>
<ul>
<li>1610: Galileo observes Jupiter's moons</li>
<li>1781: William Herschel discovers Uranus</li>
<li>1929: Edwin Hubble proves the universe is expanding</li>
<li>2015: LIGO detects gravitational waves</li>
</ul>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Fake embedding function (deterministic, no API key)
# ---------------------------------------------------------------------------

_EMBED_DIM = 128


def fake_embed_fn(text: str) -> list[float]:
    """Generate a deterministic 128-dim fake embedding from text via hashing."""
    h = hashlib.sha256(text.lower().encode()).digest()
    # Expand hash to fill 128 dimensions
    expanded = h * (_EMBED_DIM * 4 // len(h) + 1)
    values = struct.unpack(f"<{_EMBED_DIM}f", expanded[: _EMBED_DIM * 4])
    # Normalize to unit vector
    norm = math.sqrt(sum(v * v for v in values)) or 1.0
    return [v / norm for v in values]


def fake_similarity_fn(a: str, b: str) -> float:
    """Cosine similarity between fake embeddings of two texts."""
    va = fake_embed_fn(a)
    vb = fake_embed_fn(b)
    dot = sum(x * y for x, y in zip(va, vb))
    return max(0.0, min(1.0, (dot + 1.0) / 2.0))  # map [-1,1] to [0,1]


# ---------------------------------------------------------------------------
# Mock LLM functions (deterministic string manipulation)
# ---------------------------------------------------------------------------


def fake_generate_fn(query: str) -> str:
    """Mock HyDE: generate a fake hypothetical document."""
    return (
        f"Based on current scientific knowledge, {query.lower().rstrip('?')} "
        f"involves several important concepts in astrophysics and space science. "
        f"Researchers have studied this topic extensively using observations "
        f"from space telescopes and ground-based observatories."
    )


def fake_multi_query_fn(query: str, n: int = 3) -> list[str]:
    """Mock multi-query: generate query variations."""
    words = query.split()
    variations = [query]
    if len(words) > 2:
        variations.append(" ".join(words[1:]) + " " + words[0])
    variations.append(f"What is known about {query.lower().rstrip('?')}?")
    if n > 3:
        variations.append(f"Explain {query.lower().rstrip('?')} in detail")
    return variations[:n]


def fake_decompose_fn(query: str) -> list[str]:
    """Mock decomposition: split on conjunctions."""
    parts = []
    for sep in [" and ", " or ", ", "]:
        if sep in query.lower():
            parts = [p.strip() for p in query.split(sep) if p.strip()]
            break
    if not parts:
        parts = [query, f"What are the key aspects of {query.lower().rstrip('?')}?"]
    return parts


def fake_stepback_fn(query: str) -> str:
    """Mock step-back: generalize the query."""
    # Remove specific nouns and generalize
    return f"What are the fundamental principles underlying {query.lower().rstrip('?')}?"


# ---------------------------------------------------------------------------
# Pre-built stores and retrievers
# ---------------------------------------------------------------------------


def build_demo_stores() -> tuple[InMemoryVectorStore, InMemoryContextStore]:
    """Build pre-loaded vector and context stores with sample documents."""
    vector_store = InMemoryVectorStore()
    context_store = InMemoryContextStore()

    for doc in _DOCUMENTS:
        item = ContextItem(
            id=doc["id"],
            content=doc["content"],
            source=SourceType.RETRIEVAL,
            score=0.0,
            priority=5,
            token_count=len(doc["content"].split()),
            metadata={"title": doc["title"]},
        )
        context_store.add(item)
        embedding = fake_embed_fn(doc["content"])
        vector_store.add_embedding(doc["id"], embedding)

    return vector_store, context_store


def build_demo_retriever() -> tuple[Any, Any]:
    """Build pre-indexed Dense + Sparse retrievers over sample docs.

    Returns (dense_retriever, sparse_retriever).
    """
    vector_store, context_store = build_demo_stores()

    dense = DenseRetriever(
        vector_store=vector_store,
        context_store=context_store,
        embed_fn=fake_embed_fn,
    )

    sparse = SparseRetriever()
    items = [context_store.get(doc["id"]) for doc in _DOCUMENTS]
    sparse.index([item for item in items if item is not None])

    return dense, sparse


def build_evaluation_dataset() -> EvaluationDataset:
    """Build a dataset with queries and ground truth for evaluation demos."""
    samples = [
        EvaluationSample(
            query="What is the largest planet?",
            relevant_ids=["doc-006"],
        ),
        EvaluationSample(
            query="Tell me about black holes",
            relevant_ids=["doc-008"],
        ),
        EvaluationSample(
            query="How was the universe formed?",
            relevant_ids=["doc-016"],
        ),
        EvaluationSample(
            query="What are exoplanets?",
            relevant_ids=["doc-013"],
        ),
        EvaluationSample(
            query="What is dark matter and dark energy?",
            relevant_ids=["doc-014", "doc-015"],
        ),
    ]
    return EvaluationDataset(samples=samples, name="astro-demo")


def sample_conversation_turns() -> list[tuple[str, str]]:
    """Return 10 user/assistant turn pairs for memory demos."""
    return [
        ("Hi, my name is Arthur", "Nice to meet you, Arthur! How can I help you today?"),
        (
            "I'm interested in astronomy",
            "That's a fascinating field! What aspect interests you most?",
        ),
        (
            "Tell me about Mars",
            "Mars is the fourth planet from the Sun, often called the Red Planet.",
        ),
        (
            "Does it have water?",
            "Yes, Mars has water ice at its poles and subsurface ice deposits.",
        ),
        (
            "What about missions to Mars?",
            "Several rovers have explored Mars, including Curiosity and Perseverance.",
        ),
        (
            "I also like coding in Python",
            "Great choice! Python is widely used in astronomical data analysis.",
        ),
        (
            "What libraries do astronomers use?",
            "Popular ones include astropy, numpy, and matplotlib.",
        ),
        (
            "Tell me about the James Webb telescope",
            "JWST is an infrared space observatory launched in December 2021.",
        ),
        (
            "How far is it from Earth?",
            "JWST orbits at the L2 point, about 1.5 million kilometers from Earth.",
        ),
        ("Thanks for all the info!", "You're welcome, Arthur! Feel free to ask anytime."),
    ]


def sample_facts() -> list[dict[str, str]]:
    """Return 8 sample facts for memory store demos."""
    return [
        {"content": "User's name is Arthur", "tags": "personal,name"},
        {"content": "Arthur is interested in astronomy", "tags": "interests"},
        {"content": "Arthur likes coding in Python", "tags": "interests,programming"},
        {"content": "Mars has water ice at its poles", "tags": "astronomy,mars"},
        {"content": "JWST orbits at L2 point 1.5M km from Earth", "tags": "astronomy,telescope"},
        {"content": "Astronomers commonly use astropy and numpy", "tags": "programming,astronomy"},
        {"content": "The universe is 13.8 billion years old", "tags": "astronomy,cosmology"},
        {"content": "Gravitational waves were first detected in 2015", "tags": "physics,discovery"},
    ]
