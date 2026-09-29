string kind              # BOWL / CUP / "" (용기 없이 잴 때)
uint8 target_n           # 잴 횟수 (params.yaml f2.weigh_samples)
float32[] samples_g      # 지금까지 잰 값(g) — 잰 순서대로. 빈 용기 기준값(f2.empty_weight_g)을 뺀 값
bool done                # 다 쟀다 — median_g 가 유효하다
float32 median_g         # 최종 중앙값(g) — done 일 때만. 이력의 '무게 전 → 후' 와 같은 값
builtin_interfaces/Time stamp
