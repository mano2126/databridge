"""
tests/sql_converter_corpus.py
SQL 변환기 정확도 측정용 테스트 케이스.

난이도 체계:
  easy   : 단일 문장, 단순 함수 매핑 (ISNULL, TOP 등)
  medium : CTE, 서브쿼리, 여러 함수 조합
  hard   : 재귀 CTE, 윈도우 함수, 복합 JOIN
  edge   : DB 고유 문법 (MSSQL OUTPUT, PIVOT, MERGE 등)

각 케이스:
  - name: 시나리오 이름
  - src_db, tgt_db: 방언 쌍
  - input_sql: 원본 SQL
  - expected_contains: 결과에 포함되어야 할 문자열 (핵심 변환)
  - expected_not_contains: 결과에 없어야 할 문자열 (소스 방언 잔재)
  - allow_partial: True면 부분 변환도 통과 (edge case 용)
"""

CORPUS = [
    # ─────────────────────────────────────────────
    # EASY — 단일 함수 매핑
    # ─────────────────────────────────────────────
    {
        "name": "MSSQL TOP → MySQL LIMIT",
        "difficulty": "easy",
        "src_db": "mssql", "tgt_db": "mysql",
        "input_sql": "SELECT TOP 10 id, name FROM users WHERE status = 'A' ORDER BY id",
        "expected_contains": ["LIMIT 10"],
        "expected_not_contains": ["TOP 10"],
    },
    {
        "name": "MSSQL ISNULL → MySQL COALESCE",
        "difficulty": "easy",
        "src_db": "mssql", "tgt_db": "mysql",
        "input_sql": "SELECT ISNULL(comment, 'N/A') AS c FROM orders",
        "expected_contains": ["COALESCE"],
        "expected_not_contains": ["ISNULL("],
    },
    {
        "name": "MySQL IFNULL → MSSQL ISNULL",
        "difficulty": "easy",
        "src_db": "mysql", "tgt_db": "mssql",
        "input_sql": "SELECT IFNULL(col, 0) FROM t",
        "expected_contains": ["ISNULL", "COALESCE"],  # 둘 중 하나
        "expected_not_contains": ["IFNULL"],
        "expected_any": True,
    },
    {
        "name": "MSSQL GETDATE → MySQL NOW/CURRENT_TIMESTAMP",
        "difficulty": "easy",
        "src_db": "mssql", "tgt_db": "mysql",
        "input_sql": "INSERT INTO audit (created_at) VALUES (GETDATE())",
        "expected_contains": ["CURRENT_TIMESTAMP", "NOW()"],
        "expected_not_contains": ["GETDATE()"],
        "expected_any": True,
    },
    {
        "name": "MySQL LIMIT OFFSET → MSSQL OFFSET FETCH",
        "difficulty": "easy",
        "src_db": "mysql", "tgt_db": "mssql",
        "input_sql": "SELECT * FROM products ORDER BY id LIMIT 20 OFFSET 40",
        "expected_contains": ["OFFSET 40", "FETCH"],
        "expected_not_contains": ["LIMIT"],
    },

    # ─────────────────────────────────────────────
    # MEDIUM — CTE, 집계, 여러 함수
    # ─────────────────────────────────────────────
    {
        "name": "CTE + TOP → MySQL CTE + LIMIT",
        "difficulty": "medium",
        "src_db": "mssql", "tgt_db": "mysql",
        "input_sql": """WITH sales_cte AS (
            SELECT region, SUM(amount) AS total
            FROM sales GROUP BY region
        )
        SELECT TOP 5 * FROM sales_cte ORDER BY total DESC""",
        "expected_contains": ["WITH", "sales_cte", "LIMIT 5"],
        "expected_not_contains": ["TOP 5"],
    },
    {
        "name": "MSSQL STRING_AGG → MySQL GROUP_CONCAT",
        "difficulty": "medium",
        "src_db": "mssql", "tgt_db": "mysql",
        "input_sql": "SELECT region, STRING_AGG(name, ', ') AS names FROM customers GROUP BY region",
        "expected_contains": ["GROUP_CONCAT"],
        "expected_not_contains": ["STRING_AGG"],
    },
    {
        "name": "MySQL GROUP_CONCAT → PostgreSQL STRING_AGG",
        "difficulty": "medium",
        "src_db": "mysql", "tgt_db": "postgresql",
        "input_sql": "SELECT post_id, GROUP_CONCAT(tag SEPARATOR ',') FROM tags GROUP BY post_id",
        "expected_contains": ["STRING_AGG"],
        "expected_not_contains": ["GROUP_CONCAT"],
    },
    {
        "name": "MSSQL DATEADD → MySQL DATE_ADD/INTERVAL",
        "difficulty": "medium",
        "src_db": "mssql", "tgt_db": "mysql",
        "input_sql": "SELECT DATEADD(DAY, 7, GETDATE()) AS next_week",
        "expected_contains": ["INTERVAL", "DAY"],
        "expected_not_contains": ["DATEADD"],
    },
    {
        "name": "MySQL DATE_FORMAT → MSSQL FORMAT",
        "difficulty": "medium",
        "src_db": "mysql", "tgt_db": "mssql",
        "input_sql": "SELECT DATE_FORMAT(created_at, '%Y-%m-%d') FROM orders",
        "expected_contains": ["FORMAT"],
        "expected_not_contains": ["DATE_FORMAT"],
    },
    {
        "name": "Multi-statement with semicolon",
        "difficulty": "medium",
        "src_db": "mysql", "tgt_db": "mssql",
        "input_sql": "SELECT * FROM a; SELECT COUNT(*) FROM b;",
        "expected_contains": ["SELECT", "FROM a", "FROM b"],
    },

    # ─────────────────────────────────────────────
    # HARD — 윈도우 함수, 재귀 CTE, 복잡 서브쿼리
    # ─────────────────────────────────────────────
    {
        "name": "Window function ROW_NUMBER + PARTITION BY",
        "difficulty": "hard",
        "src_db": "mssql", "tgt_db": "mysql",
        "input_sql": """
        WITH ranked AS (
            SELECT id, name, salary, dept,
                ROW_NUMBER() OVER (PARTITION BY dept ORDER BY salary DESC) AS rn
            FROM employees
        )
        SELECT TOP 3 * FROM ranked WHERE rn = 1 ORDER BY salary DESC""",
        "expected_contains": ["ROW_NUMBER", "PARTITION BY", "LIMIT 3"],
        "expected_not_contains": ["TOP 3"],
    },
    {
        "name": "Recursive CTE - 조직도 역참조",
        "difficulty": "hard",
        "src_db": "mssql", "tgt_db": "postgresql",
        "input_sql": """
        WITH RECURSIVE org AS (
            SELECT id, name, manager_id, 0 AS lvl FROM employees WHERE manager_id IS NULL
            UNION ALL
            SELECT e.id, e.name, e.manager_id, org.lvl + 1
              FROM employees e JOIN org ON e.manager_id = org.id
        )
        SELECT * FROM org ORDER BY lvl""",
        "expected_contains": ["WITH RECURSIVE", "UNION ALL"],
    },
    {
        "name": "PIVOT (MSSQL 고유)",
        "difficulty": "hard",
        "src_db": "mssql", "tgt_db": "mysql",
        "input_sql": """
        SELECT * FROM (
            SELECT region, product, sales FROM orders
        ) src PIVOT (
            SUM(sales) FOR product IN ([A], [B], [C])
        ) pvt""",
        "expected_any": True,
        "expected_contains": ["SUM", "CASE", "GROUP BY"],
        "allow_partial": True,
    },

    # ─────────────────────────────────────────────
    # EDGE — 정말 어려운 케이스
    # ─────────────────────────────────────────────
    {
        "name": "MSSQL OUTPUT → (MySQL 미지원, 경고 필요)",
        "difficulty": "edge",
        "src_db": "mssql", "tgt_db": "mysql",
        "input_sql": "UPDATE orders SET status = 'done' OUTPUT inserted.id WHERE id = 1",
        "expected_warnings": True,
        "allow_partial": True,
    },
    {
        "name": "PostgreSQL ILIKE → MySQL LOWER LIKE",
        "difficulty": "edge",
        "src_db": "postgresql", "tgt_db": "mysql",
        "input_sql": "SELECT * FROM users WHERE name ILIKE '%kim%'",
        "expected_contains": ["LOWER", "LIKE"],
        "expected_not_contains": ["ILIKE"],
    },
    {
        "name": "MSSQL CROSS APPLY → MySQL (미지원, 경고)",
        "difficulty": "edge",
        "src_db": "mssql", "tgt_db": "mysql",
        "input_sql": """
        SELECT o.id, latest.price FROM orders o
        CROSS APPLY (
            SELECT TOP 1 price FROM order_history h
            WHERE h.order_id = o.id ORDER BY h.changed_at DESC
        ) latest""",
        "allow_partial": True,
        "expected_warnings": True,
    },
    {
        "name": "MSSQL MERGE INTO → MySQL INSERT ON DUPLICATE KEY",
        "difficulty": "edge",
        "src_db": "mssql", "tgt_db": "mysql",
        "input_sql": """
        MERGE INTO target USING source ON (target.id = source.id)
        WHEN MATCHED THEN UPDATE SET target.val = source.val
        WHEN NOT MATCHED THEN INSERT (id, val) VALUES (source.id, source.val);""",
        "allow_partial": True,
        "expected_warnings": True,
    },
]


def summary():
    """난이도별 집계"""
    d = {}
    for c in CORPUS:
        diff = c.get("difficulty", "medium")
        d[diff] = d.get(diff, 0) + 1
    return d
