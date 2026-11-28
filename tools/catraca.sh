#!/bin/bash
# Catraca de promoção com pré-seleção, retomável (protocolo de docs/CATRACA.md).
#
# Uso: tools/catraca.sh PASTA_SAIDA CANDIDATA1.json [CANDIDATA2.json ...]
#
# 1. Pré-seleção: cada candidata joga 32 partidas pareadas contra a oficial
#    (--fixo, sem promover). Fica a de mais pontos.
# 2. Desafio: a escolhida faz o teste sequencial com confirmação, com pares novos
#    (--offset 1000: índices de par que a pré-seleção não usou).
#
# Rode de novo depois de um reinício: cada etapa pula o que já tem resultado.json e o
# desafio continua dos pares já gravados. Rode a partir da raiz do repositório.
set -euo pipefail
OUT=${1:?pasta de saída}
shift
[ $# -ge 1 ] || { echo "dê pelo menos uma candidata" >&2; exit 2; }
mkdir -p "$OUT"
best="" best_points=-1
for cand in "$@"; do
  name=$(basename "$cand" .json)
  dir="$OUT/pre-$name"
  [ -f "$dir/resultado.json" ] || python3 -m luna promote --candidate "$cand" --fixo \
    --max-games 32 --out "$dir"
  points=$(python3 -c "import json,sys;r=json.load(open(sys.argv[1]));print(r['score']*r['games'])" \
    "$dir/resultado.json")
  echo "$name: $points pontos em 32"
  if python3 -c "import sys;sys.exit(0 if float(sys.argv[1])>float(sys.argv[2]) else 1)" \
      "$points" "$best_points"; then
    best=$cand best_points=$points
  fi
done
name=$(basename "$best" .json)
echo "$name" > "$OUT/escolhida.txt"
dir="$OUT/desafio-$name"
[ -f "$dir/resultado.json" ] || python3 -m luna promote --candidate "$best" --offset 1000 \
  --out "$dir"
cat "$dir/resultado.json"
