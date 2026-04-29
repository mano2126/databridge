<!--
  pages/MigrationReport.vue — 단일 Job 이관 완료 리포트 (v9 패치 #27 전면 재설계)

  디자인 철학:
  - 첫 페이지에서 핵심 결과 즉시 파악
  - 금융/공공 기관 제출 가능한 수준의 격식
  - 데이터 임팩트 강조
  - A4 인쇄 최적화

  3가지 스타일:
    A. 공식 결재 (formal)   — 은행/정부 결재 양식
    B. 임원 보고 (exec)      — 대시보드형, 시각화 강조
    C. 기술 상세 (technical) — 엔지니어링 근거

  라우트: /report/job/:jobId?style=formal|exec|technical
-->
<template>
  <div class="report-root" :class="'style-' + activeStyle">

    <!-- 상단 툴바 -->
    <div class="toolbar no-print">
      <div class="tb-left">
        <div class="tb-brand">
          <div class="tb-logo">DB</div>
          <div>
            <div class="tb-title">이관 실행 리포트</div>
            <div class="tb-sub">Migration Execution Report</div>
          </div>
        </div>
      </div>
      <div class="tb-center">
        <div class="style-picker">
          <button v-for="s in styles" :key="s.v"
            class="sp-btn" :class="{on: activeStyle === s.v}"
            @click="activeStyle = s.v">
            <span class="sp-ico">{{ s.icon }}</span>
            <span>{{ s.label }}</span>
          </button>
        </div>
      </div>
      <div class="tb-right">
        <button class="tb-btn primary" @click="doPrint">🖨 인쇄 / PDF 저장</button>
        <button class="tb-btn" @click="closeWindow">닫기</button>
      </div>
    </div>

    <div v-if="loading" class="loading-box"><span class="spinner"/>리포트 생성 중...</div>
    <div v-else-if="error" class="error-box"><h2>⚠ 리포트 생성 실패</h2><pre>{{ error }}</pre></div>

    <!-- PDF 뷰어 레이아웃: 좌측 썸네일 + 우측 페이지 -->
    <div v-else class="viewer-layout">
      <!-- 좌측 썸네일 사이드바 -->
      <aside class="thumbs no-print">
        <div class="thumbs-hdr">페이지</div>
        <div class="thumbs-list">
          <button v-for="(p, i) in pageList" :key="activeStyle + '-' + i"
                  class="thumb" :class="{on: currentPage === i+1}"
                  @click="scrollToPage(i+1)"
                  :title="p.title">
            <!-- 실제 페이지 DOM을 복제해서 축소 렌더 -->
            <div class="thumb-frame">
              <div :ref="el => setThumbRef(el, i)" class="thumb-scaler"></div>
              <div class="thumb-num-badge">{{ i + 1 }}</div>
            </div>
            <div class="thumb-caption">
              <span class="thumb-title-txt">{{ p.title }}</span>
              <span class="thumb-label">{{ i + 1 }} / {{ pageList.length }}</span>
            </div>
          </button>
        </div>
        <div class="thumbs-footer">
          <div class="thumb-total">총 {{ pageList.length }} 페이지</div>
          <div class="thumb-jobid mono">{{ job?.id?.slice(0, 13) }}</div>
        </div>
      </aside>

      <!-- 우측 메인 뷰 -->
      <div class="viewer-main">

    <!-- ═══ A. 공식 결재 ═══ -->
    <div v-if="activeStyle === 'formal'" class="paper formal">
      <section id="page-1" class="page formal-page-1">
        <header class="fp-header">
          <div class="fp-logo">
            <div class="fp-logo-mark">DB</div>
            <div>
              <div class="fp-logo-name">DataBridge Studio</div>
              <div class="fp-logo-sub">Enterprise Data Migration Platform</div>
            </div>
          </div>
          <div class="fp-hdr-right">
            <div class="fp-doc-num"><span>문서번호</span><b>DBS-{{ docNumber }}</b></div>
            <div class="fp-doc-date">{{ fmtDateShort(job?.finished_at || job?.started_at) }}</div>
          </div>
        </header>

        <div class="fp-title-block">
          <div class="fp-title-main">데이터베이스 이관 실행 결과 보고서</div>
          <div class="fp-title-eng">Database Migration Execution Report</div>
          <div class="fp-title-bar"></div>
        </div>

        <div class="fp-kpi-grid">
          <div class="fp-kpi" :class="{positive: !rowMismatch && tblStats.error===0}">
            <div class="fp-kpi-icon">✓</div>
            <div class="fp-kpi-lbl">이관 상태</div>
            <div class="fp-kpi-val">{{ statusLabel(job?.status) }}</div>
            <div class="fp-kpi-sub">{{ rowMismatch ? '행수 불일치' : (tblStats.error === 0 ? '전체 정상 완료' : tblStats.error + '개 오류') }}</div>
          </div>
          <div class="fp-kpi">
            <div class="fp-kpi-icon">▦</div>
            <div class="fp-kpi-lbl">테이블 수</div>
            <div class="fp-kpi-val">{{ fmtNum(tblStats.total) }}</div>
            <div class="fp-kpi-sub">성공 {{ fmtNum(tblStats.done) }} · 오류 {{ fmtNum(tblStats.error) }}</div>
          </div>
          <div class="fp-kpi">
            <div class="fp-kpi-icon">Σ</div>
            <div class="fp-kpi-lbl">총 이관 행수</div>
            <div class="fp-kpi-val">{{ fmtNum(totalRowsTgt) }}</div>
            <div class="fp-kpi-sub">소스 {{ fmtNum(totalRowsSrc) }} 행 대비 <b :class="rowMismatch ? 'warn' : 'ok'">{{ rowMismatch ? '–' + fmtNum(totalRowsSrc - totalRowsTgt) : '100%' }}</b></div>
          </div>
          <div class="fp-kpi">
            <div class="fp-kpi-icon">⏱</div>
            <div class="fp-kpi-lbl">소요 시간</div>
            <div class="fp-kpi-val">{{ fmtElapsed }}</div>
            <div class="fp-kpi-sub">평균 속도 {{ fmtNum(avgSpeed) }} rows/sec</div>
          </div>
        </div>

        <h2 class="fp-section-title"><span class="sec-num">1</span>실행 개요</h2>
        <table class="fp-meta-table">
          <tbody>
            <tr><th>작업명</th><td>{{ job?.name || '—' }}</td><th>실행자</th><td>{{ job?.created_by || 'system' }}</td></tr>
            <tr><th>Job ID</th><td colspan="3" class="mono">{{ job?.id }}</td></tr>
            <tr><th>시작일시</th><td>{{ fmtDateTime(job?.started_at) }}</td><th>완료일시</th><td>{{ fmtDateTime(job?.finished_at) }}</td></tr>
            <tr><th>소스 DB</th><td colspan="3">{{ dbLabel(job?.src_db) }} · <span class="mono">{{ job?.src_host }}:{{ job?.src_port || '-' }}</span> / <b>{{ job?.src_database }}</b></td></tr>
            <tr><th>타겟 DB</th><td colspan="3">{{ dbLabel(job?.tgt_db) }} · <span class="mono">{{ job?.tgt_host }}:{{ job?.tgt_port || '-' }}</span> / <b>{{ job?.tgt_database }}</b></td></tr>
            <tr><th>이관 엔진</th><td>{{ job?.bulk_mode || 'auto' }}</td><th>테이블 병렬</th><td>{{ job?.parallel_tables || 1 }} 개 동시</td></tr>
          </tbody>
        </table>

        <div class="fp-verdict" :class="rowMismatch || tblStats.error > 0 ? 'warn' : 'ok'">
          <div class="fp-verdict-icon">{{ rowMismatch || tblStats.error > 0 ? '⚠' : '✓' }}</div>
          <div class="fp-verdict-text">
            <b>{{ rowMismatch || tblStats.error > 0 ? '검토 필요' : '이관 정상 완료' }}</b>
            <p v-if="!rowMismatch && tblStats.error === 0">
              소스 DB 의 총 <b>{{ fmtNum(totalRowsSrc) }} 행</b>이 타겟 DB 에 누락 없이 이관되었으며,
              모든 테이블의 행수가 정확히 일치함을 확인하였습니다.
              데이터 무결성이 보장된 상태로 이관 작업이 성공적으로 완료되었습니다.
            </p>
            <p v-else>
              <span v-if="rowMismatch">소스와 타겟 간 <b>{{ fmtNum(Math.abs(totalRowsSrc - totalRowsTgt)) }} 행</b>의 차이가 발생하였습니다. </span>
              <span v-if="tblStats.error > 0"><b>{{ tblStats.error }} 개</b> 테이블에서 오류가 발생하였습니다. </span>
              상세 내용은 다음 페이지의 테이블별 명세를 참조하십시오.
            </p>
          </div>
        </div>

        <div class="fp-approval">
          <div class="fp-approval-hdr">검 토 · 승 인</div>
          <table class="fp-approval-tbl">
            <thead>
              <tr><th>작 성</th><th>검 토</th><th>승 인</th></tr>
            </thead>
            <tbody>
              <tr>
                <td class="sig-cell"><div class="sig-role">담당자</div><div class="sig-space"></div><div class="sig-date">날짜: {{ fmtDateShort(new Date().toISOString()) }}</div></td>
                <td class="sig-cell"><div class="sig-role">팀장</div><div class="sig-space"></div><div class="sig-date">날짜:</div></td>
                <td class="sig-cell"><div class="sig-role">CIO / DBA Lead</div><div class="sig-space"></div><div class="sig-date">날짜:</div></td>
              </tr>
            </tbody>
          </table>
        </div>

        <footer class="fp-footer">
          <div>본 리포트는 DataBridge Studio 가 자동 생성한 이관 실행 기록으로, 위·변조 시 추적이 가능합니다.</div>
          <div class="mono">Generated: {{ fmtDateTime(new Date().toISOString()) }} · Page 1 of {{ totalPages }}</div>
        </footer>
      </section>

      <section id="page-2" class="page formal-page-2">
        <header class="fp-page-hdr">
          <div>문서번호 DBS-{{ docNumber }}</div>
          <div>{{ job?.name }} — 테이블별 이관 명세</div>
        </header>

        <h2 class="fp-section-title"><span class="sec-num">2</span>테이블별 이관 명세</h2>

        <table class="fp-detail-table">
          <thead>
            <tr>
              <th style="width:36px">No.</th>
              <th>테이블명</th>
              <th class="num">소스 행수</th>
              <th class="num">타겟 행수</th>
              <th class="num">차이</th>
              <th class="num">소요(초)</th>
              <th class="num">속도(rows/s)</th>
              <th style="width:76px">상태</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(t, i) in tableItems" :key="t.name"
                :class="{errorRow: t.status==='error', mismatchRow: t.rows_src !== t.rows_tgt && t.status !== 'error'}">
              <td class="num">{{ i + 1 }}</td>
              <td class="mono">{{ t.name }}</td>
              <td class="num">{{ fmtNum(t.rows_src) }}</td>
              <td class="num">{{ fmtNum(t.rows_tgt) }}</td>
              <td class="num" :class="{diff: t.rows_src !== t.rows_tgt, zero: t.rows_src === t.rows_tgt}">
                {{ t.rows_src === t.rows_tgt ? '—' : fmtNum(t.rows_tgt - t.rows_src) }}
              </td>
              <td class="num">{{ t.elapsed_sec ? fmtNum(t.elapsed_sec) : '—' }}</td>
              <td class="num">{{ t.speed ? fmtNum(t.speed) : '—' }}</td>
              <td><span class="st-pill" :class="'st-' + t.status">{{ statusLabel(t.status) }}</span></td>
            </tr>
          </tbody>
          <tfoot>
            <tr class="sum-row">
              <td colspan="2">합계 ({{ tblStats.total }} 테이블)</td>
              <td class="num">{{ fmtNum(totalRowsSrc) }}</td>
              <td class="num">{{ fmtNum(totalRowsTgt) }}</td>
              <td class="num" :class="{warn: rowMismatch}">{{ rowMismatch ? fmtNum(totalRowsTgt - totalRowsSrc) : '—' }}</td>
              <td class="num">—</td>
              <td class="num">{{ fmtNum(avgSpeed) }}</td>
              <td><span class="st-pill" :class="rowMismatch || tblStats.error > 0 ? 'st-warning' : 'st-done'">{{ rowMismatch || tblStats.error > 0 ? '검토' : '정상' }}</span></td>
            </tr>
          </tfoot>
        </table>

        <footer class="fp-footer">
          <div class="mono">Page 2 of {{ totalPages }}</div>
        </footer>
      </section>

      <section id="page-3" v-if="objectItems.length > 0 || errorList.length > 0 || hasAdvisorData" class="page formal-page-3">
        <header class="fp-page-hdr">
          <div>문서번호 DBS-{{ docNumber }}</div>
          <div>{{ job?.name }} — 오브젝트 변환 및 기술 구성</div>
        </header>

        <h2 v-if="objectItems.length > 0" class="fp-section-title"><span class="sec-num">3</span>오브젝트 변환 결과</h2>
        <table v-if="objectItems.length > 0" class="fp-detail-table">
          <thead>
            <tr><th style="width:36px">No.</th><th>오브젝트명</th><th style="width:110px">유형</th><th style="width:130px">변환 엔진</th><th style="width:76px">상태</th></tr>
          </thead>
          <tbody>
            <tr v-for="(o, i) in objectItems" :key="o.name + i" :class="{errorRow: o.status==='error'}">
              <td class="num">{{ i + 1 }}</td>
              <td class="mono">{{ o.name }}</td>
              <td><span class="obj-type-pill" :class="'ot-' + o.type">{{ objTypeLabel(o.type) }}</span></td>
              <td>{{ o.engine || '—' }}</td>
              <td><span class="st-pill" :class="'st-' + o.status">{{ statusLabel(o.status) }}</span></td>
            </tr>
          </tbody>
        </table>

        <!-- v10 #23: AI DBA Consultant Before/After 실측 비교 -->
        <template v-if="hasAdvisorData">
          <h2 class="fp-section-title">
            <span class="sec-num">{{ objectItems.length > 0 ? 4 : 3 }}</span>
            AI DBA Consultant 권고 이행 결과
          </h2>

          <!-- 요약 박스 -->
          <div class="fp-advisor-summary" :class="advisorImpact.summary.overall_improvement_pct > 0 ? 'ok' : 'neutral'">
            <div class="fp-advisor-summary-icon">
              {{ advisorImpact.summary.overall_improvement_pct > 0 ? '📊' : '📋' }}
            </div>
            <div class="fp-advisor-summary-text">
              <b>{{ advisorImpact.summary.estimated_savings }}</b>
              <p>
                총 {{ advisorImpact.summary.total_recommendations }}건의 권고 중
                <strong>{{ advisorImpact.summary.applied }}건 적용</strong>,
                {{ advisorImpact.summary.skipped }}건 미적용.
                <template v-if="advisorImpact.summary.measured_count > 0">
                  이 중 <strong>{{ advisorImpact.summary.measured_count }}건</strong>에 대해 실측 데이터로 효과를 검증했습니다.
                </template>
              </p>
            </div>
          </div>

          <!-- 적용한 권고 — Before/After 비교표 -->
          <template v-if="advisorImpact.applied.length > 0">
            <h3 class="fp-subsection">적용한 권고 — Before / After 비교</h3>
            <table class="fp-advisor-table">
              <thead>
                <tr>
                  <th style="width:10%">심각도</th>
                  <th style="width:28%">권고</th>
                  <th style="width:18%">Before (예상)</th>
                  <th style="width:18%">After (실측)</th>
                  <th style="width:16%">개선 효과</th>
                  <th style="width:10%">판정</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(item, idx) in advisorImpact.applied" :key="idx"
                    :class="'tone-' + impactTone(item)">
                  <td>
                    <span class="sev-badge" :style="{background: severityColor(item.severity)}">
                      {{ severityLabel(item.severity) }}
                    </span>
                  </td>
                  <td>
                    <div class="rec-title">{{ item.title || '(제목 없음)' }}</div>
                    <div class="rec-desc">{{ item.description || '' }}</div>
                  </td>
                  <td v-if="item.impact && item.impact.status === 'measured'" class="num-cell">
                    {{ fmtImpactValue(item.impact.expected_without_rec, item.impact.unit) }}
                  </td>
                  <td v-else class="num-cell">—</td>

                  <td v-if="item.impact && item.impact.status === 'measured'" class="num-cell emph">
                    {{ fmtImpactValue(item.impact.actual, item.impact.unit) }}
                  </td>
                  <td v-else class="num-cell">—</td>

                  <td v-if="item.impact && item.impact.status === 'measured'" class="num-cell">
                    <div class="saved-pct" :class="impactTone(item)">
                      <template v-if="item.impact.saved_pct > 0">
                        ▼ {{ item.impact.saved_pct.toFixed(1) }}%
                      </template>
                      <template v-else>
                        ▲ {{ Math.abs(item.impact.saved_pct).toFixed(1) }}%
                      </template>
                    </div>
                    <div class="saved-abs">
                      {{ fmtImpactValue(Math.abs(item.impact.saved_absolute), item.impact.unit) }}
                      {{ item.impact.saved_pct > 0 ? '절감' : '증가' }}
                    </div>
                  </td>
                  <td v-else class="num-cell">
                    <span class="muted">실측 미매핑</span>
                  </td>

                  <td class="verdict-cell">
                    <template v-if="impactTone(item) === 'good'"><span class="v-good">✓ 개선</span></template>
                    <template v-else-if="impactTone(item) === 'bad'"><span class="v-bad">⚠ 저하</span></template>
                    <template v-else><span class="v-neutral">—</span></template>
                  </td>
                </tr>
              </tbody>
            </table>
          </template>

          <!-- 적용 안 한 권고 — 놓친 이득 -->
          <template v-if="advisorImpact.skipped.length > 0">
            <h3 class="fp-subsection">미적용 권고 — 놓친 개선 기회</h3>
            <table class="fp-advisor-table muted-table">
              <thead>
                <tr>
                  <th style="width:10%">심각도</th>
                  <th style="width:40%">권고</th>
                  <th style="width:25%">예상했던 개선</th>
                  <th style="width:25%">실제 상태</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(item, idx) in advisorImpact.skipped" :key="idx">
                  <td>
                    <span class="sev-badge" :style="{background: severityColor(item.severity)}">
                      {{ severityLabel(item.severity) }}
                    </span>
                  </td>
                  <td>
                    <div class="rec-title">{{ item.title || '(제목 없음)' }}</div>
                    <div class="rec-desc">{{ item.description || '' }}</div>
                  </td>
                  <td v-if="item.impact && item.impact.status === 'missed_opportunity'" class="num-cell">
                    ▼ {{ item.impact.missed_saving_pct.toFixed(1) }}%
                    <div class="saved-abs muted">
                      ({{ fmtImpactValue(item.impact.missed_saving_absolute, item.impact.unit) }})
                    </div>
                  </td>
                  <td v-else class="num-cell"><span class="muted">추정치 없음</span></td>

                  <td v-if="item.impact && item.impact.status === 'missed_opportunity'" class="num-cell">
                    {{ fmtImpactValue(item.impact.actual, item.impact.unit) }} 소요
                  </td>
                  <td v-else class="num-cell">—</td>
                </tr>
              </tbody>
            </table>
          </template>

          <!-- Job 실측 메트릭 간단 표시 -->
          <div v-if="advisorImpact.job_metrics" class="fp-advisor-metrics">
            <h3 class="fp-subsection">Job 실측 데이터</h3>
            <div class="metric-grid">
              <div class="metric-item" v-if="advisorImpact.job_metrics.total_duration_sec">
                <div class="m-label">총 이관 시간</div>
                <div class="m-value">{{ fmtImpactValue(advisorImpact.job_metrics.total_duration_sec, 'sec') }}</div>
              </div>
              <div class="metric-item" v-if="advisorImpact.job_metrics.rows_per_sec">
                <div class="m-label">평균 처리 속도</div>
                <div class="m-value">{{ Math.round(advisorImpact.job_metrics.rows_per_sec).toLocaleString() }} rows/s</div>
              </div>
              <div class="metric-item" v-if="advisorImpact.job_metrics.rows_total">
                <div class="m-label">총 처리 건수</div>
                <div class="m-value">{{ advisorImpact.job_metrics.rows_total.toLocaleString() }} rows</div>
              </div>
            </div>
          </div>
        </template>

        <h2 class="fp-section-title"><span class="sec-num">{{ (hasAdvisorData ? 1 : 0) + (objectItems.length > 0 ? 4 : 3) }}</span>기술 구성 및 적용 규칙</h2>
        <table class="fp-config-table">
          <tbody>
            <tr><th>이관 엔진 (bulk_mode)</th><td>{{ job?.bulk_mode || 'auto' }}</td><th>Bulk 전환 임계값</th><td>{{ fmtNum(job?.bulk_threshold_rows) }} rows</td></tr>
            <tr><th>배치 크기</th><td>{{ fmtNum(job?.batch_size) }}</td><th>테이블 병렬도</th><td>{{ job?.parallel_tables || 1 }}</td></tr>
            <tr><th>MSSQL Recovery 튜닝</th><td :class="{applied: job?.mssql_tuning}">{{ job?.mssql_tuning ? '✓ BULK_LOGGED 적용' : '미적용' }}</td>
                <th>대용량 인덱스 DISABLE</th><td :class="{applied: job?.mssql_disable_indexes}">{{ job?.mssql_disable_indexes ? '✓ 적용' : '미적용' }}</td></tr>
            <tr><th>DDL 변환 엔진</th><td>{{ job?.ddl_engine || 'rule-based' }}</td><th>오브젝트 변환 엔진</th><td>{{ job?.obj_engine || 'rule-based' }}</td></tr>
            <tr><th>오류 처리</th><td>{{ {skip:'오류 행 건너뜀',retry:'재시도 후 건너뜀',abort:'즉시 중단'}[job?.on_error] || job?.on_error }}</td>
                <th>문자 인코딩</th><td>UTF-16LE + BIN2 Collation</td></tr>
          </tbody>
        </table>

        <template v-if="errorList.length > 0">
          <h2 class="fp-section-title"><span class="sec-num">{{ (hasAdvisorData ? 1 : 0) + (objectItems.length > 0 ? 5 : 4) }}</span>오류 상세</h2>
          <table class="fp-detail-table">
            <thead>
              <tr><th style="width:36px">No.</th><th>대상</th><th>오류 메시지</th></tr>
            </thead>
            <tbody>
              <tr v-for="(e, i) in errorList" :key="e.name + i" class="errorRow">
                <td class="num">{{ i + 1 }}</td>
                <td class="mono">{{ e.name }}</td>
                <td class="err-msg">{{ e.message }}</td>
              </tr>
            </tbody>
          </table>
        </template>

        <footer class="fp-footer">
          <div class="mono">Page {{ totalPages }} of {{ totalPages }} · END OF REPORT</div>
        </footer>
      </section>
    </div>

    <!-- ═══ B. 임원 보고 ═══ -->
    <div v-else-if="activeStyle === 'exec'" class="paper exec">
      <section id="page-1" class="page">
        <div class="exec-label">MIGRATION REPORT / EXECUTIVE SUMMARY</div>
        <h1 class="exec-title">{{ job?.name || '이관 작업' }}</h1>
        <div class="exec-subtitle">
          {{ dbLabel(job?.src_db) }} {{ job?.src_database }}
          <span class="exec-arrow">→</span>
          {{ dbLabel(job?.tgt_db) }} {{ job?.tgt_database }}
        </div>
        <div class="exec-meta">
          <span>{{ fmtDateTime(job?.started_at) }}</span>
          <span class="dot">·</span>
          <span>{{ fmtElapsed }}</span>
          <span class="dot">·</span>
          <span class="st-tag" :class="'st-' + job?.status">{{ statusLabel(job?.status) }}</span>
        </div>

        <div class="exec-hero-kpi">
          <div class="ehk-main">
            <div class="ehk-main-lbl">이관된 행수</div>
            <div class="ehk-main-val">{{ fmtNum(totalRowsTgt) }}</div>
            <div class="ehk-main-sub" :class="{ok: !rowMismatch, warn: rowMismatch}">
              {{ rowMismatch ? '⚠ ' + fmtNum(Math.abs(totalRowsSrc - totalRowsTgt)) + ' 행 불일치' : '✓ 소스 대비 100% 일치' }}
            </div>
          </div>
          <div class="ehk-side">
            <div class="ehk-item"><div class="ehk-item-val">{{ fmtNum(tblStats.total) }}</div><div class="ehk-item-lbl">테이블</div></div>
            <div class="ehk-item"><div class="ehk-item-val">{{ fmtNum(avgSpeed) }}</div><div class="ehk-item-lbl">rows/sec</div></div>
            <div class="ehk-item"><div class="ehk-item-val">{{ fmtElapsed }}</div><div class="ehk-item-lbl">소요</div></div>
          </div>
        </div>

        <h3 class="exec-sec-ttl">테이블 현황 ({{ tblStats.total }})</h3>
        <div class="exec-tbl">
          <div class="et-hdr">
            <span>테이블</span><span class="num">소스</span><span class="num">타겟</span><span class="num">속도</span><span>상태</span>
          </div>
          <div v-for="t in tableItems" :key="t.name" class="et-row" :class="{err: t.status==='error', mism: t.rows_src !== t.rows_tgt}">
            <span class="mono">{{ t.name }}</span>
            <span class="num">{{ fmtNum(t.rows_src) }}</span>
            <span class="num">{{ fmtNum(t.rows_tgt) }}</span>
            <span class="num muted">{{ t.speed ? fmtNum(t.speed) : '—' }}</span>
            <span><span class="exec-pill" :class="'st-' + t.status">{{ statusLabel(t.status) }}</span></span>
          </div>
        </div>
      </section>
    </div>

    <!-- ═══ C. 기술 상세 ═══ -->
    <div v-else-if="activeStyle === 'technical'" class="paper technical">
      <section id="page-1" class="page">
        <div class="tech-header">
          <div class="tech-code">DBS-{{ docNumber }}</div>
          <h1 class="tech-title">Migration Execution Report — Technical</h1>
          <div class="tech-subtitle mono">{{ job?.id }}</div>
        </div>

        <div class="tech-block">
          <div class="tech-kv"><span>Job Name</span><b>{{ job?.name }}</b></div>
          <div class="tech-kv"><span>Status</span><b :class="'st-' + job?.status">{{ statusLabel(job?.status) }}</b></div>
          <div class="tech-kv"><span>Started</span><b>{{ fmtDateTime(job?.started_at) }}</b></div>
          <div class="tech-kv"><span>Finished</span><b>{{ fmtDateTime(job?.finished_at) }}</b></div>
          <div class="tech-kv"><span>Elapsed</span><b>{{ fmtElapsed }}</b></div>
          <div class="tech-kv"><span>Source</span><b class="mono">{{ dbLabel(job?.src_db) }} {{ job?.src_host }}:{{ job?.src_port }} / {{ job?.src_database }}</b></div>
          <div class="tech-kv"><span>Target</span><b class="mono">{{ dbLabel(job?.tgt_db) }} {{ job?.tgt_host }}:{{ job?.tgt_port }} / {{ job?.tgt_database }}</b></div>
        </div>

        <div class="tech-metrics">
          <div class="tm"><div class="tm-v">{{ fmtNum(tblStats.total) }}</div><div>Tables</div></div>
          <div class="tm"><div class="tm-v">{{ fmtNum(totalRowsTgt) }}</div><div>Rows Inserted</div></div>
          <div class="tm"><div class="tm-v">{{ fmtNum(avgSpeed) }}</div><div>avg rows/sec</div></div>
          <div class="tm"><div class="tm-v">{{ fmtNum(tblStats.error) }}</div><div>Errors</div></div>
        </div>

        <h3 class="tech-sec">Per-Table Breakdown</h3>
        <table class="tech-table">
          <thead><tr><th>#</th><th>Table</th><th>src</th><th>tgt</th><th>Δ</th><th>rows/s</th><th>state</th></tr></thead>
          <tbody>
            <tr v-for="(t, i) in tableItems" :key="t.name" :class="{err: t.status==='error'}">
              <td>{{ i+1 }}</td>
              <td class="mono">{{ t.name }}</td>
              <td class="num">{{ fmtNum(t.rows_src) }}</td>
              <td class="num">{{ fmtNum(t.rows_tgt) }}</td>
              <td class="num" :class="{diff: t.rows_src !== t.rows_tgt}">{{ t.rows_src === t.rows_tgt ? '0' : fmtNum(t.rows_tgt - t.rows_src) }}</td>
              <td class="num">{{ t.speed ? fmtNum(t.speed) : '—' }}</td>
              <td>{{ t.status }}</td>
            </tr>
          </tbody>
        </table>

        <h3 class="tech-sec">Configuration</h3>
        <pre class="tech-code-block">bulk_mode            = {{ job?.bulk_mode || 'auto' }}
bulk_threshold_rows  = {{ fmtNum(job?.bulk_threshold_rows) }}
batch_size           = {{ fmtNum(job?.batch_size) }}
parallel_tables      = {{ job?.parallel_tables || 1 }}
mssql_tuning         = {{ job?.mssql_tuning ? 'true' : 'false' }}
mssql_disable_indexes= {{ job?.mssql_disable_indexes ? 'true' : 'false' }}
ddl_engine           = {{ job?.ddl_engine || 'rule-based' }}
obj_engine           = {{ job?.obj_engine || 'rule-based' }}
on_error             = {{ job?.on_error || 'skip' }}
encoding             = UTF-16LE (BIN2 collation)</pre>
      </section>
    </div>

      </div><!-- /viewer-main -->
    </div><!-- /viewer-layout -->
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'

const route = useRoute()
const job = ref(null)
const verifyReport = ref(null)   // v10 #23: Before/After 비교용
const loading = ref(true)
const error = ref('')

const styles = [
  { v: 'formal',    label: '공식 결재',  icon: '📜' },
  { v: 'exec',      label: '임원 보고',  icon: '✦' },
  { v: 'technical', label: '기술 상세',  icon: '⚙' },
]
const activeStyle = ref(route.query.style || 'formal')

async function load() {
  loading.value = true
  try {
    const jid = route.params.jobId || route.params.jid
    const r = await axios.get(`/api/v1/jobs/${jid}`)
    job.value = r.data

    // v10 #23: verify 리포트 호출 (advisor_impact 포함)
    //   실패해도 기본 리포트는 렌더됨 (하위 호환)
    try {
      const v = await axios.get(`/api/v1/report/verify/${jid}`)
      verifyReport.value = v.data
    } catch (ve) {
      console.warn('[report] verify API 실패 (advisor_impact 없이 렌더):', ve?.message)
    }
  } catch (e) {
    error.value = e.response?.data?.detail || e.message
  } finally {
    loading.value = false
  }
}

function doPrint() { window.print() }

// v10: 닫기 버튼 — 새 탭/창을 안전하게 닫음
// 브라우저 정책상 window.close() 는 "스크립트로 열린 창"에서만 동작.
// 라우터 navigation 으로 연 새 탭에서는 window.close() 가 무시되므로,
// 1) window.close() 시도
// 2) 실패 시 window.open('','_self').close() (일부 브라우저)
// 3) 그래도 실패 시 history.back() (방문 기록이 있으면)
// 4) 최후: 사용자에게 Ctrl+W 안내
function closeWindow() {
  try { window.close() } catch {}
  // window.close() 후에도 창이 남아있으면 다른 방법 시도
  setTimeout(() => {
    if (!window.closed) {
      try {
        // 일부 브라우저에서 동작
        window.open('', '_self')
        window.close()
      } catch {}
      setTimeout(() => {
        if (!window.closed) {
          // 히스토리가 있으면 뒤로 가기 (리포트가 이전 페이지에서 열린 경우)
          if (window.history.length > 1) {
            window.history.back()
          } else {
            alert('브라우저 정책상 자동으로 닫을 수 없습니다.\n탭을 직접 닫아주세요 (Ctrl+W 또는 ⌘+W).')
          }
        }
      }, 100)
    }
  }, 100)
}

const DB_LABELS = {
  mysql:'MySQL', mariadb:'MariaDB', aurora:'Aurora MySQL', tidb:'TiDB',
  mssql:'MSSQL', azure:'Azure SQL', oracle:'Oracle', postgresql:'PostgreSQL',
}
function dbLabel(k) { return DB_LABELS[(k||'').toLowerCase()] || (k||'').toUpperCase() }

function fmtNum(n) { if (n == null || n === '') return '—'; return Number(n).toLocaleString() }

function fmtDateTime(s) {
  if (!s) return '—'
  const d = new Date(s)
  return d.getFullYear() + '. ' +
    String(d.getMonth()+1).padStart(2,'0') + '. ' +
    String(d.getDate()).padStart(2,'0') + '.  ' +
    String(d.getHours()).padStart(2,'0') + ':' +
    String(d.getMinutes()).padStart(2,'0') + ':' +
    String(d.getSeconds()).padStart(2,'0')
}
function fmtDateShort(s) {
  if (!s) return '—'
  const d = new Date(s)
  return d.getFullYear() + '. ' + String(d.getMonth()+1).padStart(2,'0') + '. ' + String(d.getDate()).padStart(2,'0') + '.'
}

const fmtElapsed = computed(() => {
  if (!job.value?.started_at) return '—'
  const start = new Date(job.value.started_at).getTime()
  const end = job.value.finished_at ? new Date(job.value.finished_at).getTime() : Date.now()
  const sec = Math.round((end - start) / 1000)
  if (sec < 60) return sec + '초'
  const m = Math.floor(sec / 60), s = sec % 60
  if (m < 60) return m + '분 ' + s + '초'
  const h = Math.floor(m / 60), mm = m % 60
  return h + '시간 ' + mm + '분'
})

function statusLabel(s) {
  return {completed:'완료', done:'완료', error:'오류', running:'진행중',
          idle:'대기', pending:'대기', paused:'일시정지', aborted:'중단'}[s] || (s || '—')
}
function objTypeLabel(t) {
  return {procedure:'프로시저', function:'함수', trigger:'트리거', view:'뷰'}[t] || (t || '—').toUpperCase()
}

const docNumber = computed(() => {
  if (!job.value?.id) return '—'
  const d = job.value.started_at ? new Date(job.value.started_at) : new Date()
  const ymd = d.getFullYear().toString().slice(-2) + String(d.getMonth()+1).padStart(2,'0') + String(d.getDate()).padStart(2,'0')
  return ymd + '-' + job.value.id.slice(0,4).toUpperCase()
})

const tableItems = computed(() => {
  const st = job.value?.item_statuses || {}
  const tables = job.value?.tables || []
  return tables.map(name => {
    const s = st[name] || {}
    let elapsed_sec = null
    if (s.started_at && s.finished_at) {
      elapsed_sec = Math.round((new Date(s.finished_at) - new Date(s.started_at)) / 1000)
    }
    return {
      name,
      status: s.status || 'pending',
      rows_src: Number(s.rows_src || s.rows || 0),
      rows_tgt: Number(s.rows_tgt || 0),
      speed: Number(s.speed || 0),
      elapsed_sec,
      error: s.error || null,
    }
  })
})

const objectItems = computed(() => {
  const st = job.value?.item_statuses || {}
  const objs = job.value?.objects || {}
  const result = []
  const push = (type, list) => {
    for (const name of (list || [])) {
      const s = st[name] || {}
      result.push({ name, type, status: s.status || 'pending', engine: s.engine || job.value?.obj_engine || 'rule-based' })
    }
  }
  push('procedure', objs.procedures)
  push('function',  objs.functions)
  push('trigger',   objs.triggers)
  push('view',      objs.views)
  return result
})

const errorList = computed(() => {
  const result = []
  const st = job.value?.item_statuses || {}
  for (const [name, s] of Object.entries(st)) {
    if (s.status === 'error' && s.error) {
      result.push({ name, message: s.error })
    }
  }
  return result
})

const tblStats = computed(() => {
  const items = tableItems.value
  return {
    total: items.length,
    done:  items.filter(t => t.status === 'done' || t.status === 'completed').length,
    error: items.filter(t => t.status === 'error').length,
  }
})

const totalRowsSrc = computed(() => tableItems.value.reduce((s,t) => s + t.rows_src, 0))
const totalRowsTgt = computed(() => tableItems.value.reduce((s,t) => s + t.rows_tgt, 0))
const rowMismatch  = computed(() => totalRowsSrc.value !== totalRowsTgt.value)
const avgSpeed     = computed(() => Number(job.value?.speed) || 0)
const totalPages   = computed(() => (objectItems.value.length > 0 || errorList.value.length > 0 || hasAdvisorData.value) ? 3 : 2)

// v10 #23: AI DBA Consultant Before/After
const advisorImpact = computed(() => {
  const ai = verifyReport.value?.advisor_impact
  if (!ai || !ai.has_data) return null
  return ai
})
const hasAdvisorData = computed(() => !!advisorImpact.value)

// 개선/저하를 판정 (음수 절감은 "오히려 느려짐" 으로 표시)
function impactTone(item) {
  const imp = item?.impact
  if (!imp) return 'neutral'
  if (imp.status === 'measured') {
    return imp.saved_pct > 5 ? 'good' :
           imp.saved_pct > -5 ? 'neutral' : 'bad'
  }
  if (imp.status === 'missed_opportunity') {
    return imp.missed_saving_pct > 5 ? 'warn' : 'neutral'
  }
  return 'neutral'
}

// 단위 표시 보정 (초 → 분으로 변환)
function fmtImpactValue(v, unit) {
  if (v == null) return '-'
  if (unit === 'sec' && Math.abs(v) >= 120) {
    return `${(v/60).toFixed(1)}분`
  }
  if (unit === 'sec') return `${Math.round(v)}초`
  return `${v} ${unit || ''}`
}

function severityLabel(s) {
  return ({high: '심각', med: '중요', low: '참고'})[s] || s || '-'
}
function severityColor(s) {
  return ({high: '#dc2626', med: '#f59e0b', low: '#0284c7'})[s] || '#6b7280'
}

// v9 패치 #28: PDF 뷰어 썸네일
const currentPage = ref(1)
const thumbRefs = ref({})   // 인덱스 → DOM 요소

function setThumbRef(el, idx) {
  if (el) thumbRefs.value[idx] = el
  else delete thumbRefs.value[idx]
}

const pageList = computed(() => {
  if (activeStyle.value === 'formal') {
    const list = [
      { n: 1, title: '요약 · 결재' },
      { n: 2, title: '테이블 명세' },
    ]
    if (objectItems.value.length > 0 || errorList.value.length > 0 || hasAdvisorData.value) {
      // v10 #23: advisor_impact 있으면 제목 더 명확하게
      const p3title = hasAdvisorData.value
        ? (objectItems.value.length > 0 ? '오브젝트 · AI 권고 · 설정' : 'AI 권고 · 설정')
        : '오브젝트 · 설정'
      list.push({ n: 3, title: p3title })
    }
    return list
  }
  if (activeStyle.value === 'exec') {
    return [{ n: 1, title: '임원 요약' }]
  }
  return [{ n: 1, title: '기술 상세' }]
})

// 실제 페이지 DOM 을 복제해서 썸네일에 삽입 + scale
async function renderThumbnails() {
  await nextTick()
  // 약간의 지연 후 실행 (페이지 내용이 완전히 렌더링될 시간)
  await new Promise(r => setTimeout(r, 100))

  for (const [idxStr, container] of Object.entries(thumbRefs.value)) {
    const i = parseInt(idxStr)
    if (!container) continue
    const pageEl = document.getElementById('page-' + (i + 1))
    if (!pageEl) continue
    // 기존 내용 제거
    container.innerHTML = ''
    // 원본 페이지를 복제 (딥)
    const clone = pageEl.cloneNode(true)
    // 복제본에서 id 제거 (중복 방지)
    clone.removeAttribute('id')
    clone.querySelectorAll('[id]').forEach(e => e.removeAttribute('id'))
    // 썸네일 프레임 크기 측정 후 scale 계산
    const frame = container.parentElement  // .thumb-frame
    const frameW = frame?.clientWidth || 140
    // 원본 페이지 너비 ≈ 210mm ≈ 794px (@96dpi)
    const originalW = 794
    const scale = frameW / originalW
    // 복제본에 고정 크기 + scale 적용
    clone.style.width = originalW + 'px'
    clone.style.minHeight = '1123px'  // A4 height
    clone.style.transform = 'scale(' + scale + ')'
    clone.style.transformOrigin = 'top left'
    clone.style.pointerEvents = 'none'
    // 버튼/입력 등 비활성
    container.appendChild(clone)
  }
}

function scrollToPage(n) {
  const el = document.getElementById('page-' + n)
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'start' })
    currentPage.value = n
  }
}

// 스크롤 시 현재 페이지 추적
function _trackScroll() {
  const pages = pageList.value.map(p => document.getElementById('page-' + p.n)).filter(Boolean)
  if (!pages.length) return
  const viewerMain = document.querySelector('.viewer-main')
  if (!viewerMain) return
  const scrollTop = viewerMain.scrollTop
  const midline = scrollTop + viewerMain.clientHeight / 3
  let active = 1
  for (let i = 0; i < pages.length; i++) {
    if (pages[i].offsetTop <= midline) active = i + 1
  }
  if (active !== currentPage.value) currentPage.value = active
}

onMounted(() => {
  load().then(() => {
    // 스크롤 리스너는 viewer-main 에 바인딩
    setTimeout(() => {
      const viewerMain = document.querySelector('.viewer-main')
      if (viewerMain) viewerMain.addEventListener('scroll', _trackScroll)
      renderThumbnails()
    }, 300)
  })
})

// 스타일 변경 시 페이지 DOM 이 바뀌므로 썸네일 재생성
watch(activeStyle, async () => {
  await nextTick()
  await new Promise(r => setTimeout(r, 150))
  renderThumbnails()
  currentPage.value = 1
})

// 윈도우 크기 변경 시 썸네일 scale 재계산
onMounted(() => {
  const onResize = () => {
    clearTimeout(window._thumbRenderTimer)
    window._thumbRenderTimer = setTimeout(renderThumbnails, 200)
  }
  window.addEventListener('resize', onResize)
})
</script>

<style scoped>
.report-root {
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Malgun Gothic','Pretendard',sans-serif;
  background:#2a2d34; color:#111;
  display:flex; flex-direction:column;
  /* v9 패치 #29b: body/html 의 스크롤을 이 root 가 가로챔 */
  position:fixed; top:0; left:0; right:0; bottom:0;
  overflow:hidden;
}

/* v9 패치 #28: PDF 뷰어 레이아웃 */
.viewer-layout {
  flex:1; display:flex;
  min-height:0;   /* flex child 에서 overflow 가 동작하려면 필수 */
  overflow:hidden;
}
.thumbs {
  width:180px; background:#1a1d23; color:#d1d5db;
  flex-shrink:0; display:flex; flex-direction:column;
  border-right:1px solid rgba(0,0,0,0.3);
  height:100%;   /* 부모 viewer-layout 높이 기준 */
  overflow:hidden;
}
.thumbs-hdr {
  padding:14px 18px; font-size:11px; letter-spacing:2px;
  font-weight:700; color:#9ca3af; text-transform:uppercase;
  border-bottom:1px solid rgba(255,255,255,0.05);
}
.thumbs-list { flex:1; overflow-y:auto; padding:14px 12px; display:flex; flex-direction:column; gap:12px; }
.thumb {
  background:transparent; border:0; cursor:pointer; padding:0;
  display:flex; flex-direction:column; gap:4px; align-items:center;
}
.thumb-frame {
  /* A4 비율 (210/297) 유지 */
  width:100%;
  aspect-ratio:210/297;
  background:#fff;
  border:2px solid transparent;
  border-radius:3px;
  box-shadow:0 2px 8px rgba(0,0,0,0.3);
  position:relative;
  overflow:hidden;
  transition:all .15s;
}
.thumb:hover .thumb-frame { border-color:#60a5fa; box-shadow:0 4px 12px rgba(96,165,250,0.4); }
.thumb.on .thumb-frame { border-color:#3b82f6; box-shadow:0 4px 14px rgba(59,130,246,0.5); }
.thumb-scaler {
  /* 복제된 페이지 DOM 이 여기에 들어감 */
  /* scale 은 JS에서 inline 스타일로 적용 */
  position:absolute; top:0; left:0;
  width:100%; height:100%;
  overflow:hidden;
}
.thumb-scaler > * { /* 복제된 .page 요소 */
  pointer-events:none;
  user-select:none;
}
.thumb-num-badge {
  position:absolute; top:4px; right:4px;
  background:#1e3a8a; color:#fff; font-size:9px; font-weight:700;
  width:16px; height:16px; border-radius:50%;
  display:flex; align-items:center; justify-content:center;
  z-index:2;
  box-shadow:0 1px 3px rgba(0,0,0,0.3);
}
.thumb.on .thumb-num-badge { background:#3b82f6; }
.thumb-caption {
  width:100%; display:flex; flex-direction:column; gap:1px;
  align-items:center; padding:2px 4px;
}
.thumb-title-txt {
  font-size:10px; color:#e5e7eb; font-weight:600;
  text-align:center; line-height:1.2;
}
.thumb.on .thumb-title-txt { color:#60a5fa; }
.thumb-label {
  font-size:9px; color:#6b7280; font-family:'Consolas',monospace;
}
.thumb.on .thumb-label { color:#60a5fa; }
.thumbs-footer {
  padding:12px 16px; border-top:1px solid rgba(255,255,255,0.05);
  font-size:9.5px; color:#9ca3af;
}
.thumb-total { font-weight:600; margin-bottom:2px; }
.thumb-jobid { font-size:8.5px; color:#6b7280; word-break:break-all; }

.viewer-main {
  flex:1; overflow-y:auto; background:#2a2d34; padding:24px 0;
  min-height:0;   /* v9 #29b: 중요 — flex 에서 overflow 동작 */
  height:100%;
  /* v10: 스크롤바 가시성 강화 (WebKit/Blink) */
  scrollbar-width: auto;
  scrollbar-color: #8b92a1 #1e2028;
}
.viewer-main::-webkit-scrollbar {
  width: 14px;
  height: 14px;
}
.viewer-main::-webkit-scrollbar-track {
  background: #1e2028;
  border-left: 1px solid #3a3d44;
}
.viewer-main::-webkit-scrollbar-thumb {
  background: #6b7280;
  border: 3px solid #1e2028;
  border-radius: 7px;
  min-height: 40px;
}
.viewer-main::-webkit-scrollbar-thumb:hover {
  background: #9ca3af;
}
.viewer-main::-webkit-scrollbar-thumb:active {
  background: #d1d5db;
}
.viewer-main::-webkit-scrollbar-corner {
  background: #1e2028;
}

.toolbar {
  background:#fff; padding:12px 22px;
  display:flex; align-items:center; gap:16px; border-bottom:1px solid rgba(0,0,0,0.3);
  z-index:100;
}
.tb-brand { display:flex; align-items:center; gap:10px; }
.tb-logo {
  width:34px; height:34px; border-radius:8px;
  background:linear-gradient(135deg,#1e3a8a,#3b82f6);
  color:#fff; font-weight:800; font-size:13px;
  display:flex; align-items:center; justify-content:center;
}
.tb-title { font-size:15px; font-weight:700; color:#111; line-height:1.2; }
.tb-sub { font-size:10px; color:#6b7280; letter-spacing:0.5px; }
.tb-center { flex:1; display:flex; justify-content:center; }
.style-picker { display:flex; gap:3px; background:#f3f4f6; padding:3px; border-radius:10px; }
.sp-btn { padding:7px 16px; font-size:12.5px; border-radius:8px; border:0; background:transparent; cursor:pointer; color:#6b7280; display:flex; align-items:center; gap:6px; font-weight:500; }
.sp-btn.on { background:#fff; color:#111; box-shadow:0 1px 3px rgba(0,0,0,0.1); font-weight:600; }
.sp-ico { font-size:13px; }
.tb-btn { padding:8px 14px; font-size:12.5px; border:1px solid #e5e7eb; border-radius:8px; background:#fff; cursor:pointer; font-weight:500; color:#374151; }
.tb-btn:hover { background:#f9fafb; }
.tb-btn.primary { background:#111; color:#fff; border-color:#111; }
.tb-btn.primary:hover { background:#1f2937; }

.loading-box, .error-box { padding:80px 20px; text-align:center; font-size:14px; color:#6b7280; }
.spinner { display:inline-block; width:18px; height:18px; border:2px solid #d1d5db; border-top-color:#3b82f6; border-radius:50%; animation:spin 1s linear infinite; margin-right:10px; vertical-align:middle; }
@keyframes spin { to { transform: rotate(360deg); } }

.paper { max-width:210mm; margin:24px auto; background:#fff; box-shadow:0 2px 20px rgba(0,0,0,0.08); }
.page { padding:18mm 16mm 14mm; min-height:297mm; box-sizing:border-box; page-break-after:always; position:relative; }
.page:last-child { page-break-after:auto; }
.mono { font-family:'SFMono-Regular','Consolas','Monaco',monospace; }

/* ═══ 공식 결재 ═══ */
.formal { color:#111827; }
.fp-header { display:flex; justify-content:space-between; align-items:center; padding-bottom:8mm; border-bottom:2px solid #1e3a8a; }
.fp-logo { display:flex; align-items:center; gap:10px; }
.fp-logo-mark { width:38px; height:38px; border-radius:8px; background:linear-gradient(135deg,#1e3a8a,#2563eb); color:#fff; font-weight:800; font-size:14px; display:flex; align-items:center; justify-content:center; }
.fp-logo-name { font-weight:700; font-size:11.5pt; color:#1e3a8a; line-height:1.1; }
.fp-logo-sub { font-size:8.5pt; color:#6b7280; letter-spacing:0.5px; margin-top:2px; }
.fp-hdr-right { text-align:right; }
.fp-doc-num { font-size:9pt; color:#374151; margin-bottom:2mm; }
.fp-doc-num span { color:#9ca3af; margin-right:6px; font-size:8.5pt; }
.fp-doc-num b { font-family:'Consolas',monospace; font-size:10pt; color:#1e3a8a; }
.fp-doc-date { font-size:9pt; color:#6b7280; font-family:'Consolas',monospace; }

.fp-title-block { text-align:center; margin:12mm 0 10mm; }
.fp-title-main { font-size:20pt; font-weight:800; color:#111; letter-spacing:-0.5px; line-height:1.3; }
.fp-title-eng { font-size:9.5pt; color:#6b7280; margin-top:3mm; letter-spacing:1.5px; }
.fp-title-bar { width:50mm; height:2px; background:#1e3a8a; margin:5mm auto; }

.fp-kpi-grid { display:grid; grid-template-columns:repeat(4, 1fr); gap:3mm; margin:0 0 10mm; }
.fp-kpi { background:#f9fafb; border:1px solid #e5e7eb; border-radius:6px; padding:4mm 3mm; position:relative; overflow:hidden; }
.fp-kpi.positive { background:linear-gradient(135deg,#f0fdf4,#f9fafb); border-color:#86efac; }
.fp-kpi-icon { position:absolute; top:3mm; right:3mm; width:8mm; height:8mm; border-radius:50%; background:#e5e7eb; color:#6b7280; display:flex; align-items:center; justify-content:center; font-size:12pt; font-weight:700; }
.fp-kpi.positive .fp-kpi-icon { background:#22c55e; color:#fff; }
.fp-kpi-lbl { font-size:8.5pt; color:#6b7280; font-weight:500; letter-spacing:0.3px; }
.fp-kpi-val { font-size:18pt; font-weight:700; color:#111; margin:2mm 0 1mm; line-height:1.1; letter-spacing:-0.5px; }
.fp-kpi-sub { font-size:8.5pt; color:#374151; line-height:1.4; }
.fp-kpi-sub b.ok { color:#059669; }
.fp-kpi-sub b.warn { color:#dc2626; }

.fp-section-title { font-size:12.5pt; font-weight:700; color:#1e3a8a; margin:8mm 0 4mm; padding-bottom:2mm; border-bottom:1.5px solid #1e3a8a; display:flex; align-items:center; gap:6px; }
.fp-section-title .sec-num { background:#1e3a8a; color:#fff; width:22px; height:22px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:10.5pt; font-weight:700; }

.fp-meta-table { width:100%; border-collapse:collapse; font-size:10pt; margin-bottom:6mm; }
.fp-meta-table th { background:#f9fafb; color:#374151; font-weight:600; padding:2.5mm 3mm; border:1px solid #e5e7eb; text-align:left; width:22%; }
.fp-meta-table td { padding:2.5mm 3mm; border:1px solid #e5e7eb; color:#111; }

.fp-verdict { margin:6mm 0; padding:4mm 5mm; border-radius:6px; display:flex; gap:4mm; align-items:flex-start; }
.fp-verdict.ok { background:#f0fdf4; border:1px solid #86efac; }
.fp-verdict.warn { background:#fef2f2; border:1px solid #fca5a5; }
.fp-verdict-icon { font-size:18pt; font-weight:700; line-height:1; }
.fp-verdict.ok .fp-verdict-icon { color:#059669; }
.fp-verdict.warn .fp-verdict-icon { color:#dc2626; }
.fp-verdict-text { flex:1; }
.fp-verdict-text b { font-size:11pt; color:#111; display:block; margin-bottom:2mm; }
.fp-verdict-text p { margin:0; font-size:10pt; line-height:1.7; color:#374151; }

.fp-approval { margin-top:10mm; }
.fp-approval-hdr { font-size:10pt; color:#1e3a8a; font-weight:700; letter-spacing:3pt; text-align:center; padding:2mm; background:#eff6ff; border-radius:3px; margin-bottom:3mm; }
.fp-approval-tbl { width:100%; border-collapse:collapse; }
.fp-approval-tbl th { background:#1e3a8a; color:#fff; padding:2mm; font-size:10pt; font-weight:600; letter-spacing:1pt; width:33.33%; border-right:1px solid rgba(255,255,255,0.2); }
.fp-approval-tbl th:last-child { border-right:0; }
.sig-cell { border:1px solid #d1d5db; padding:3mm; vertical-align:top; }
.sig-role { font-size:9pt; color:#6b7280; margin-bottom:2mm; }
.sig-space { height:18mm; }
.sig-date { font-size:8.5pt; color:#9ca3af; border-top:1px solid #e5e7eb; padding-top:1.5mm; font-family:'Consolas',monospace; }

.fp-footer { position:absolute; bottom:8mm; left:16mm; right:16mm; padding-top:2mm; border-top:0.5px solid #d1d5db; display:flex; justify-content:space-between; font-size:8pt; color:#9ca3af; }

.fp-page-hdr { display:flex; justify-content:space-between; padding-bottom:3mm; margin-bottom:8mm; border-bottom:1px solid #e5e7eb; font-size:9pt; color:#6b7280; }
.fp-page-hdr div:last-child { font-weight:600; color:#1e3a8a; }

.fp-detail-table { width:100%; border-collapse:collapse; font-size:9.5pt; }
.fp-detail-table th { background:#1e3a8a; color:#fff; padding:2mm 2.5mm; text-align:left; font-weight:600; font-size:9pt; letter-spacing:0.3pt; }
.fp-detail-table th.num { text-align:right; }
.fp-detail-table td { padding:1.8mm 2.5mm; border-bottom:0.5px solid #e5e7eb; }
.fp-detail-table td.num { text-align:right; font-variant-numeric:tabular-nums; font-family:'Consolas',monospace; font-size:9pt; }
.fp-detail-table td.diff:not(.zero) { color:#dc2626; font-weight:700; }
.fp-detail-table td.zero { color:#9ca3af; }
.fp-detail-table tr.errorRow { background:#fef2f2; }
.fp-detail-table tr.errorRow td { color:#991b1b; }
.fp-detail-table tr.mismatchRow { background:#fefce8; }
.fp-detail-table tr.sum-row { background:#f9fafb; font-weight:700; border-top:2px solid #1e3a8a; }
.fp-detail-table tr.sum-row td { border-bottom:0; padding-top:2.5mm; padding-bottom:2.5mm; }
.fp-detail-table td.num.warn { color:#dc2626; }
.fp-detail-table td.err-msg { font-family:'Consolas',monospace; font-size:8.5pt; color:#991b1b; word-break:break-all; }

.st-pill { display:inline-block; padding:1.5px 8px; border-radius:10px; font-size:8.5pt; font-weight:600; letter-spacing:0.3pt; white-space:nowrap; }
.st-pill.st-done, .st-pill.st-completed { background:#d1fae5; color:#065f46; }
.st-pill.st-error { background:#fee2e2; color:#991b1b; }
.st-pill.st-running { background:#dbeafe; color:#1e40af; }
.st-pill.st-pending { background:#f3f4f6; color:#6b7280; }
.st-pill.st-warning, .st-pill.st-aborted { background:#fef3c7; color:#92400e; }
.obj-type-pill { display:inline-block; padding:1.5px 8px; border-radius:10px; background:#eef2ff; color:#4338ca; font-size:8.5pt; font-weight:600; }
.obj-type-pill.ot-procedure { background:#fef3c7; color:#92400e; }
.obj-type-pill.ot-function { background:#dbeafe; color:#1e40af; }
.obj-type-pill.ot-trigger { background:#fde68a; color:#78350f; }
.obj-type-pill.ot-view { background:#ddd6fe; color:#5b21b6; }

.fp-config-table { width:100%; border-collapse:collapse; font-size:9.5pt; margin-bottom:6mm; }
.fp-config-table th { background:#f9fafb; color:#374151; font-weight:600; padding:2.2mm 3mm; border:1px solid #e5e7eb; text-align:left; width:25%; }
.fp-config-table td { padding:2.2mm 3mm; border:1px solid #e5e7eb; color:#111; font-family:'Consolas',monospace; font-size:9pt; }
.fp-config-table td.applied { color:#059669; font-weight:700; font-family:inherit; }

/* ═══ v10 #23: AI DBA Consultant Before/After 섹션 ═══ */
.fp-advisor-summary {
  display:flex; gap:4mm; align-items:flex-start;
  padding:4mm 5mm; margin:4mm 0 6mm;
  border-radius:6px; border:1.5px solid;
}
.fp-advisor-summary.ok { background:#f0fdf4; border-color:#86efac; }
.fp-advisor-summary.neutral { background:#f9fafb; border-color:#d1d5db; }
.fp-advisor-summary-icon { font-size:18pt; line-height:1; flex-shrink:0; }
.fp-advisor-summary-text { flex:1; }
.fp-advisor-summary-text b { font-size:11pt; color:#111; display:block; margin-bottom:2mm; }
.fp-advisor-summary-text p { margin:0; font-size:9.5pt; line-height:1.6; color:#374151; }
.fp-advisor-summary-text strong { color:#1e3a8a; font-weight:700; }

.fp-subsection {
  font-size:10.5pt; font-weight:600; color:#1e3a8a;
  margin:5mm 0 2.5mm; padding-left:2mm;
  border-left:3px solid #1e3a8a;
}

.fp-advisor-table { width:100%; border-collapse:collapse; font-size:9.5pt; margin-bottom:5mm; }
.fp-advisor-table th { background:#1e3a8a; color:#fff; padding:2.2mm 2.5mm; text-align:left; font-weight:600; font-size:9pt; }
.fp-advisor-table td { padding:2.2mm 2.5mm; border-bottom:0.5px solid #e5e7eb; vertical-align:top; }
.fp-advisor-table td.num-cell { text-align:right; font-variant-numeric:tabular-nums; font-family:'Consolas',monospace; }
.fp-advisor-table td.num-cell.emph { color:#1e3a8a; font-weight:700; }
.fp-advisor-table tr.tone-good { background:#f0fdf4; }
.fp-advisor-table tr.tone-bad { background:#fef2f2; }
.fp-advisor-table tr.tone-warn { background:#fefce8; }
.fp-advisor-table .rec-title { font-weight:600; color:#111; margin-bottom:1mm; }
.fp-advisor-table .rec-desc { font-size:8.5pt; color:#6b7280; line-height:1.4; }
.fp-advisor-table.muted-table { opacity:0.85; }

.sev-badge {
  display:inline-block; padding:1px 6px; color:#fff; font-size:8pt; font-weight:600;
  border-radius:3px; letter-spacing:0.2pt;
}
.saved-pct { font-weight:700; font-size:10pt; }
.saved-pct.good { color:#059669; }
.saved-pct.bad { color:#dc2626; }
.saved-pct.neutral { color:#6b7280; }
.saved-abs { font-size:8.5pt; color:#6b7280; margin-top:0.5mm; }
.saved-abs.muted { opacity:0.7; }
.verdict-cell { text-align:center; font-weight:700; font-size:9pt; }
.v-good { color:#059669; }
.v-bad { color:#dc2626; }
.v-neutral { color:#9ca3af; }
.muted { color:#9ca3af; font-style:italic; font-size:8.5pt; }

.fp-advisor-metrics { margin-top:4mm; padding:3mm 4mm; background:#f9fafb; border-radius:5px; }
.metric-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:4mm; margin-top:2mm; }
.metric-item { text-align:center; padding:2mm; background:#fff; border:0.5px solid #e5e7eb; border-radius:4px; }
.m-label { font-size:8.5pt; color:#6b7280; margin-bottom:1.5mm; }
.m-value { font-size:11pt; font-weight:700; color:#1e3a8a; font-variant-numeric:tabular-nums; }

/* ═══ 임원 보고 ═══ */
.exec { font-family:-apple-system,BlinkMacSystemFont,sans-serif; }
.exec .page { padding:22mm 18mm; }
.exec-label { font-size:9.5pt; color:#3b82f6; font-weight:700; letter-spacing:2pt; margin-bottom:6mm; }
.exec-title { font-size:26pt; font-weight:800; color:#111; line-height:1.1; margin:0 0 4mm; letter-spacing:-1pt; }
.exec-subtitle { font-size:12pt; color:#374151; font-weight:500; margin-bottom:4mm; }
.exec-arrow { color:#3b82f6; font-weight:700; margin:0 6px; }
.exec-meta { font-size:10pt; color:#6b7280; display:flex; gap:10px; align-items:center; margin-bottom:10mm; flex-wrap:wrap; }
.exec-meta .dot { color:#d1d5db; }
.st-tag { padding:2px 10px; border-radius:12px; font-weight:600; font-size:9pt; }
.st-tag.st-completed, .st-tag.st-done { background:#d1fae5; color:#065f46; }
.st-tag.st-error { background:#fee2e2; color:#991b1b; }

.exec-hero-kpi { display:grid; grid-template-columns:1.8fr 1fr; gap:5mm; margin-bottom:12mm; padding:8mm; background:linear-gradient(135deg,#1e3a8a,#1e40af); border-radius:12px; color:#fff; }
.ehk-main-lbl { font-size:10pt; color:#bfdbfe; font-weight:500; letter-spacing:0.5pt; }
.ehk-main-val { font-size:40pt; font-weight:800; line-height:1; margin:3mm 0; letter-spacing:-2pt; }
.ehk-main-sub { font-size:11pt; font-weight:500; }
.ehk-main-sub.ok { color:#6ee7b7; }
.ehk-main-sub.warn { color:#fca5a5; }
.ehk-side { display:flex; flex-direction:column; gap:4mm; justify-content:center; }
.ehk-item { padding:3mm 5mm; background:rgba(255,255,255,0.1); border-radius:6px; }
.ehk-item-val { font-size:16pt; font-weight:700; color:#fff; line-height:1; }
.ehk-item-lbl { font-size:9pt; color:#bfdbfe; margin-top:1mm; }

.exec-sec-ttl { font-size:14pt; font-weight:700; color:#111; margin:0 0 5mm; }
.exec-tbl { border:1px solid #e5e7eb; border-radius:10px; overflow:hidden; }
.et-hdr, .et-row { display:grid; grid-template-columns:2.5fr 1fr 1fr 1fr 1fr; padding:3mm 5mm; align-items:center; font-size:10pt; }
.et-hdr { background:#f9fafb; color:#6b7280; font-size:9pt; font-weight:600; letter-spacing:0.3pt; border-bottom:1px solid #e5e7eb; }
.et-hdr .num, .et-row .num { text-align:right; font-variant-numeric:tabular-nums; font-family:'Consolas',monospace; font-size:9.5pt; }
.et-row { border-bottom:0.5px solid #f3f4f6; }
.et-row:last-child { border-bottom:0; }
.et-row .muted { color:#9ca3af; }
.et-row.err { background:#fef2f2; }
.et-row.mism { background:#fefce8; }
.exec-pill { padding:1.5px 8px; border-radius:8px; font-size:8.5pt; font-weight:600; }
.exec-pill.st-done, .exec-pill.st-completed { background:#d1fae5; color:#065f46; }
.exec-pill.st-error { background:#fee2e2; color:#991b1b; }

/* ═══ 기술 상세 ═══ */
.technical { font-family:-apple-system,sans-serif; }
.tech-header { padding-bottom:6mm; border-bottom:2px solid #111; margin-bottom:8mm; }
.tech-code { font-family:'Consolas',monospace; font-size:10pt; color:#6b7280; }
.tech-title { font-size:22pt; font-weight:700; color:#111; margin:2mm 0; letter-spacing:-0.5pt; }
.tech-subtitle { font-size:9.5pt; color:#6b7280; }
.tech-block { display:grid; grid-template-columns:1fr 1fr; gap:2mm 8mm; margin-bottom:8mm; }
.tech-kv { display:flex; justify-content:space-between; padding:2mm 0; border-bottom:0.5px solid #e5e7eb; font-size:10pt; }
.tech-kv span { color:#6b7280; }
.tech-kv b { color:#111; text-align:right; font-weight:600; }
.tech-kv b.st-completed, .tech-kv b.st-done { color:#059669; }
.tech-kv b.st-error { color:#dc2626; }
.tech-metrics { display:grid; grid-template-columns:repeat(4,1fr); gap:3mm; margin-bottom:8mm; }
.tm { background:#111; color:#fff; padding:4mm; border-radius:6px; text-align:center; }
.tm-v { font-size:20pt; font-weight:700; line-height:1; margin-bottom:2mm; letter-spacing:-0.5pt; }
.tm > div:last-child { font-size:9pt; color:#9ca3af; letter-spacing:0.5pt; }
.tech-sec { font-size:12pt; font-weight:700; color:#111; margin:6mm 0 3mm; padding-bottom:1mm; border-bottom:1px solid #d1d5db; }
.tech-table { width:100%; border-collapse:collapse; font-size:9.5pt; }
.tech-table th { background:#111; color:#fff; padding:2mm 3mm; text-align:left; font-weight:600; font-size:9pt; }
.tech-table td { padding:1.8mm 3mm; border-bottom:0.5px solid #e5e7eb; }
.tech-table td.num { text-align:right; font-variant-numeric:tabular-nums; font-family:'Consolas',monospace; }
.tech-table td.diff { color:#dc2626; font-weight:700; }
.tech-table tr.err { background:#fef2f2; }
.tech-code-block { background:#0f172a; color:#e2e8f0; padding:5mm; font-family:'Consolas',monospace; font-size:9pt; border-radius:6px; overflow:auto; line-height:1.7; margin:3mm 0; }

@media print {
  .no-print { display:none !important; }
  .report-root { background:#fff; display:block; height:auto; }
  .viewer-layout { display:block; height:auto; overflow:visible; }
  .viewer-main { overflow:visible; padding:0; background:#fff; }
  .paper { box-shadow:none; margin:0; max-width:none; }
  .page { padding:14mm 14mm 12mm; min-height:auto; }
  @page { size:A4; margin:0; }
}
</style>
