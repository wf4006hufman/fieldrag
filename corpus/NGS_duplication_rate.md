# NGS Duplication Rate 정리

## 요약

Duplication rate는 시퀀싱된 read 중 **동일한 원본 DNA 분자(fragment)에서 유래한 중복 read의 비율**을 의미한다. 높은 duplication rate는 곧 **library complexity(라이브러리 복잡도)가 낮다**는 신호이며, dedup 후 남는 *usable read*가 줄어들기 때문에 실질 coverage와 variant calling 신뢰도에 직접적인 영향을 준다.

핵심은 두 가지로 나눠서 봐야 한다:
- **어떤 downstream 분석에 영향을 미치는가** (영향을 주는 쪽)
- **어떤 실험적/기술적 요인 때문에 높게 나오는가** (영향을 받는 쪽)

---

## 1. Duplication의 종류

같은 "duplication"이라도 발생 원인이 다르며, 대응 방법도 다르다.

| 종류 | 원인 | 검출 기준 |
|------|------|-----------|
| **PCR duplicate** | 라이브러리 증폭 중 동일 분자가 여러 copy로 복제됨 | 동일 mapping 좌표(start/end, strand) |
| **Optical / cluster duplicate** | 하나의 cluster가 인접 위치에 중복 판독됨 (patterned flow cell의 ExAmp 반응) | flow cell 상 물리적 거리 |
| **Sequencing / natural duplicate** | 서로 다른 분자가 우연히 같은 좌표에 매핑 (deep + small target에서 흔함) | 좌표 기준으로는 구분 불가 → UMI 필요 |

> Illumina patterned flow cell(NovaSeq, NovaSeq X 등)에서는 **optical duplicate가 unpatterned 대비 상대적으로 더 두드러질 수 있다.** ExAmp 기반 cluster 생성 과정에서 exclusion amplification이 인접 well로 번지는 경우가 있어, `pixel distance` 기반 optical dedup 파라미터 튜닝이 중요하다.

---

## 2. Duplication rate가 높으면 영향을 미치는 부분 (Downstream Impact)

### 2.1 Effective / Usable Coverage 감소
가장 직접적인 영향이다. 예를 들어 raw 100x라도 dup rate 40%면 dedup 후 실질 coverage는 60x 수준으로 떨어진다. **비용을 지불하고 확보한 read 중 상당수가 버려지는 것**과 같다.

### 2.2 Variant Calling 신뢰도 저하
- Duplicate는 **독립적인 관측(independent observation)이 아니다.** 같은 원본 분자에서 온 read이므로, dedup 없이 depth를 계산하면 **거짓된 confidence**가 생긴다.
- DRAGEN을 포함한 대부분의 caller는 duplicate flag된 read를 pileup에서 제외한다. 따라서 raw depth는 높아 보여도 **실제 calling에 쓰이는 depth는 낮아** 민감도(sensitivity)가 떨어질 수 있다.

### 2.3 Somatic / Low-VAF 검출에서의 왜곡 (가장 민감)
- ctDNA, liquid biopsy, TSO500 같은 low-VAF 영역에서는 PCR duplicate가 **VAF(allele frequency) 추정을 왜곡**한다.
- 특정 분자가 과증폭되면(**jackpot effect / PCR jackpotting**) 실제로는 1개 분자에서 온 변이가 여러 read로 보여 **false positive**를 유발하거나, 반대로 low-frequency true variant를 가릴 수 있다.
- 이 때문에 low-VAF 워크플로우는 **UMI(Unique Molecular Identifier)** 기반 consensus calling을 사용해 좌표만으로 구분 불가능한 중복까지 collapse 한다.

### 2.4 Coverage Uniformity 악화
증폭 편향(amplification bias)이 심하면 특정 영역만 duplicate가 몰려 coverage가 불균일해지고, GC-rich/AT-rich 영역의 dropout이 심해진다.

### 2.5 Library Complexity 지표로서의 의미
높은 dup rate는 그 자체로 **라이브러리가 unique 분자를 충분히 담고 있지 못하다**는 진단 지표다. Picard의 `ESTIMATED_LIBRARY_SIZE`, Preseq의 complexity curve 등으로 "더 시퀀싱해도 unique read가 얼마나 늘어날지"를 예측할 수 있다.

### 2.6 비용 효율 저하
dup으로 버려지는 read는 곧 **낭비된 시퀀싱 yield**다. 재시퀀싱해도 라이브러리 복잡도가 근본 원인이면 dup만 늘고 unique read는 거의 안 늘어난다(saturation).

### 2.7 RNA-seq / scRNA-seq에서의 주의점
- **RNA-seq에서는 높은 dup rate가 반드시 문제는 아니다.** 고발현 유전자는 자연적으로 같은 좌표의 read를 많이 만들기 때문에, 순진하게 좌표 기반 dedup을 하면 오히려 **정량이 왜곡**된다.
- scRNA-seq(10x 등)에서는 **UMI + cell barcode**로 중복을 collapse하는 것이 표준이므로, "PCR duplicate"의 문제는 UMI 단계에서 처리된다. 여기서 dup rate가 높다는 것은 오히려 **sequencing saturation이 높다(라이브러리를 충분히 깊게 읽었다)**는 신호로 해석될 수 있다.

---

## 3. Duplication rate가 높게 나오는 원인 (Root Causes)

### 3.1 낮은 input / 낮은 라이브러리 복잡도
- **input DNA/RNA 양이 적을수록** 초기 unique 분자 수가 적어, 동일 분자를 반복해서 읽을 확률이 올라간다.
- cfDNA, single-cell, FFPE, LCM 시료처럼 **본질적으로 input이 적은 시료**에서 흔하다.

### 3.2 과증폭 (Over-amplification)
- PCR cycle 수가 많을수록 동일 분자의 copy가 늘어난다.
- 특히 low-input에서 cycle을 늘려 보상하려 하면 dup rate가 급격히 올라간다. → **input 늘리기 > cycle 늘리기**가 원칙.

### 3.3 Over-sequencing (복잡도 대비 과도한 depth)
- 라이브러리가 담고 있는 unique 분자 수보다 **더 깊게 시퀀싱하면**, 남는 read는 결국 이미 읽은 분자의 중복일 수밖에 없다.
- 작은 target(amplicon, small panel)을 deep하게 읽을 때 자연적으로 dup rate가 높아지는 이유이기도 하다.

### 3.4 Small insert size / 좁은 fragment 분포
- fragment size 분포가 좁으면 서로 다른 분자라도 start/end 좌표가 겹치기 쉬워, 좌표 기반 dedup이 이들을 duplicate로 오판한다.
- **paired-end + 적절한 insert size 분포**가 이를 완화한다.

### 3.5 Patterned flow cell의 optical duplicate
- 위 1절 참고. NovaSeq 계열 patterned flow cell에서 ExAmp cluster가 인접 well로 번지면 optical dup이 증가한다.
- over-loading(cluster density 과다)도 optical dup을 악화시킨다.

### 3.6 시료 품질 저하 (Degraded / FFPE)
- FFPE처럼 분해·손상된 시료는 amplifiable한 unique 분자가 적어, 결과적으로 복잡도가 낮고 dup이 높다.

### 3.7 작은 target region + high depth 조합
- 타겟 패널이 작을수록 좌표가 겹칠 확률이 높아 **자연적 duplicate**가 증가한다. 이건 실험 실패가 아니라 설계상 예상되는 현상이므로, UMI 없이는 과대평가된다.

### 3.8 Dedup 방법론 자체의 차이
- **좌표 기반 dedup**(Picard MarkDuplicates, samtools markdup, DRAGEN 기본 dedup)은 서로 다른 분자를 duplicate로 오판할 수 있다.
- **UMI 기반 dedup**은 분자 태그로 구분하므로 훨씬 정확하다. → 같은 데이터라도 **어떤 기준으로 세느냐에 따라 dup rate 숫자가 달라진다.** 리포트 해석 시 반드시 방법론을 확인해야 한다.

---

## 4. 진단 & 대응 가이드

| 상황 | 의심 원인 | 대응 |
|------|-----------|------|
| Raw depth는 높은데 dedup 후 급감 | 낮은 복잡도 / over-amplification | input 증량, PCR cycle 감소, PCR-free 검토 |
| Patterned flow cell에서 dup 급증 | optical duplicate | cluster density 조정, optical dup pixel distance 확인 |
| small panel deep seq에서 dup 높음 | 자연적 중복 | UMI 도입 후 consensus 기반 재평가 |
| low-VAF에서 false positive 의심 | PCR jackpotting | UMI consensus calling 적용 |
| RNA-seq에서 dup 높음 | 고발현 유전자 / 정상 현상 | 좌표 dedup 강제 금지, saturation으로 해석 |
| 재시퀀싱해도 unique 안 늘어남 | 복잡도 saturation | 라이브러리 재제작 (재시퀀싱은 무의미) |

---

## 5. 핵심 정리 (한 줄 요약)

- Duplication rate는 **라이브러리 복잡도의 프록시 지표**이며, 높으면 usable coverage와 variant calling 신뢰도(특히 low-VAF)에 직접 타격을 준다.
- 원인은 크게 **① 낮은 input/복잡도 ② 과증폭 ③ 과도한 depth ④ optical(patterned flow cell) ⑤ 작은 target ⑥ dedup 방법론** 으로 나뉜다.
- **숫자 자체보다 "어떤 기준(좌표 vs UMI)으로, 어떤 assay(WGS vs panel vs RNA)에서" 나온 값인지**를 먼저 확인해야 오해석을 피할 수 있다.