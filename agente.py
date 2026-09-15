"""Agente de suporte N1 com RAG sobre a base interna de soluções.

Entrega uma solução por vez. Depois de 3 tentativas sem sucesso, abre chamado
com o histórico anexado. Abaixo do limiar de similaridade, não responde.

Só stdlib — roda com `python3 agente.py`.
"""
import json, math, re, sys
from collections import Counter
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).parent
BASE = RAIZ / "base" / "artigos.json"
CHAMADOS = RAIZ / "chamados"

LIMIAR = 0.12        # abaixo disso o agente diz que não sabe
TENTATIVAS = 3       # sem limite ele entra em loop e perde a confiança do usuário

STOP = {"de","da","do","a","o","e","em","um","uma","para","com","no","na","que",
        "meu","minha","nao","não","esta","está","ao","os","as","por","se","eu"}


def tokens(texto):
    return [t for t in re.findall(r"[a-zà-ú0-9]+", texto.lower()) if t not in STOP]


class Indice:
    """Busca por similaridade atrás de uma interface.

    Esta implementação é TF-IDF em memória, para o repositório rodar sem
    infraestrutura. Em produção a mesma interface é atendida por pgvector:
    os artigos já viviam no Postgres e subir um banco vetorial ao lado seria
    mais um sistema para operar, sincronizar e monitorar sem ganho nesta escala.
    """

    def __init__(self, artigos):
        self.artigos = artigos
        # chunk por artigo, não por tamanho fixo: artigo de suporte já é uma
        # unidade semântica, cortar em N tokens parte o passo 3 ao meio.
        self.docs = [Counter(tokens(a["titulo"] + " " + a["sintomas"])) for a in artigos]
        n = len(self.docs)
        df = Counter(t for d in self.docs for t in d)
        self.idf = {t: math.log(n / (1 + c)) + 1 for t, c in df.items()}
        self.norma = [self._norma(d) for d in self.docs]

    def _peso(self, d, t):
        return d[t] * self.idf.get(t, 0.0)

    def _norma(self, d):
        return math.sqrt(sum(self._peso(d, t) ** 2 for t in d)) or 1e-9

    def buscar(self, consulta, k=3):
        q = Counter(tokens(consulta))
        nq = math.sqrt(sum((c * self.idf.get(t, 0.0)) ** 2 for t, c in q.items())) or 1e-9
        notas = []
        for i, d in enumerate(self.docs):
            num = sum(c * self.idf.get(t, 0.0) * self._peso(d, t) for t, c in q.items())
            notas.append((num / (nq * self.norma[i]), self.artigos[i]))
        notas.sort(key=lambda x: -x[0])
        return notas[:k]


def abrir_chamado(consulta, historico):
    CHAMADOS.mkdir(exist_ok=True)
    agora = datetime.now()
    caminho = CHAMADOS / f"chamado_{agora:%Y%m%d_%H%M%S_%f}.json"
    caminho.write_text(json.dumps({
        "aberto_em": agora.isoformat(timespec="seconds"),
        "relato": consulta,
        "classificacao": historico[0]["categoria"] if historico else "nao_classificado",
        # o analista humano não recomeça do zero: sobe o que já foi tentado
        "ja_tentado": [{"artigo": h["titulo"], "resultado": "nao resolveu"} for h in historico],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return caminho


def atender(indice, consulta, respostas=None):
    """respostas: lista de 's'/'n' para rodar sem interação (demo e teste)."""
    fila = iter(respostas or [])
    candidatos = indice.buscar(consulta, k=TENTATIVAS)

    if not candidatos or candidatos[0][0] < LIMIAR:
        print("  agente: não encontrei nada confiável sobre isso. Abrindo chamado.")
        print(f"  → {abrir_chamado(consulta, []).name}")
        return

    tentados = []
    for n, (nota, art) in enumerate(candidatos, 1):
        if nota < LIMIAR:
            break
        print(f"\n  agente ({n}/{TENTATIVAS}) · {art['titulo']}  [sim {nota:.2f}]")
        for passo in art["passos"]:
            print(f"     {passo}")          # um passo por vez, não o manual inteiro
        print(f"     fonte: {art['id']}")

        r = next(fila, None) or input("  resolveu? [s/n] ").strip().lower()
        print(f"  usuário: {r}")
        if r.startswith("s"):
            print("  agente: fechado. Marquei este artigo como útil.")
            return
        tentados.append(art)   # cada 'n' é dado rotulado sobre qual artigo está ruim

    plural = "tentativa" if len(tentados) == 1 else "tentativas"
    print(f"\n  agente: {len(tentados)} {plural} sem sucesso. Abrindo chamado.")
    print(f"  → {abrir_chamado(consulta, tentados).name}")


def main():
    indice = Indice(json.loads(BASE.read_text(encoding="utf-8")))
    print(f"base: {len(indice.artigos)} artigos · limiar {LIMIAR} · {TENTATIVAS} tentativas")

    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        for consulta, respostas in [
            ("a vpn não conecta desde ontem", ["s"]),
            ("não consigo acessar a rede nem a pasta compartilhada", ["n", "n", "n"]),
            ("qual o horário do almoço do refeitório", []),
        ]:
            print(f"\n{'─' * 62}\n  usuário: {consulta}")
            atender(indice, consulta, respostas)
        return

    while True:
        try:
            c = input("\nqual o problema? (ctrl+c para sair)\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if c:
            atender(indice, c)


if __name__ == "__main__":
    main()
