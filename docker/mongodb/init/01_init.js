// ============================================================
// DataBridge Studio — MongoDB 테스트 데이터
// ============================================================
db = db.getSiblingDB('testdb');

// 고객 컬렉션
db.B01_Customer.insertMany([
  { cust_name: '김민준', birth_date: new Date('1985-03-15'), gender: 'M',
    mobile: '010-1234-5678', email: 'minjun.kim@email.com', credit_score: 820, use_yn: 'Y' },
  { cust_name: '이서연', birth_date: new Date('1990-07-22'), gender: 'F',
    mobile: '010-2345-6789', email: 'seoyeon.lee@email.com', credit_score: 750, use_yn: 'Y' },
  { cust_name: '박지호', birth_date: new Date('1978-11-08'), gender: 'M',
    mobile: '010-3456-7890', email: 'jiho.park@email.com', credit_score: 680, use_yn: 'Y' },
]);

// 대출 상품 컬렉션
db.B02_LoanProduct.insertMany([
  { prod_name: '직장인 신용대출', prod_type: 'CREDIT',
    min_rate: 3.50, max_rate: 8.90, min_term: 12, max_term: 60,
    max_amount: 50000000, use_yn: 'Y' },
  { prod_name: '주택담보대출', prod_type: 'MORTGAGE',
    min_rate: 2.80, max_rate: 5.50, min_term: 60, max_term: 360,
    max_amount: 500000000, use_yn: 'Y' },
]);

print('✅ MongoDB testdb 초기화 완료');
print('B01_Customer: ' + db.B01_Customer.countDocuments() + '건');
print('B02_LoanProduct: ' + db.B02_LoanProduct.countDocuments() + '건');
