#!/usr/bin/env node

// Local P0 demonstration only. All identities, amounts, and messages here are synthetic.
const { createHash } = require('node:crypto');
const assert = require('node:assert/strict');

const state = {
  source: null,
  draft: null,
  records: [],
  audit: [],
};

const syntheticInbound = {
  messageId: 'synthetic-msg-001',
  userId: 'synthetic-user-001',
  conversationId: 'synthetic-conversation-001',
  // Fictional payment message: the amount and unit are intentionally explicit.
  text: 'دریافت ۵۰۰٬۰۰۰ تومان بابت خدمات نمونه',
};

function fingerprint(value) {
  return createHash('sha256').update(value).digest('hex');
}

function receive(message) {
  state.source = {
    sourceId: `source-${message.messageId}`,
    userId: message.userId,
    body: message.text,
    fingerprint: fingerprint(message.text),
    status: 'active_draft',
  };
  state.draft = {
    draftId: 'draft-001',
    userId: message.userId,
    direction: 'incoming',
    amountRaw: '۵۰۰٬۰۰۰',
    unitRaw: 'تومان',
    purpose: 'خدمات نمونه',
    classification: null,
    status: 'needs_clarification',
  };
  return [
    'پیام دریافت شد. چند لحظه صبر کنید…',
    'پیش‌نویس دریافت وجه آماده است. مبلغ: ۵۰۰٬۰۰۰ تومان؛ بابت: خدمات نمونه.',
    'این دریافت کدام است؟ فروش، وصول طلب، انتقال، وام/سرمایه، سایر، یا نامشخص؟',
  ];
}

function answerMaterialQuestion(answer) {
  const classifications = {
    'فروش': 'sale',
    'وصول طلب': 'receivable_collection',
    'انتقال': 'personal_or_inter_account_transfer',
    'وام/سرمایه': 'loan_or_capital',
    'سایر': 'other',
    'نامشخص': 'unknown',
  };
  assert.equal(state.draft.status, 'needs_clarification');
  assert.ok(classifications[answer], 'classification must be an allowed explicit choice');
  state.draft.classification = classifications[answer];
  state.draft.status = 'awaiting_confirmation';
  return 'پیش‌نویس نهایی: دریافت ۵۰۰٬۰۰۰ تومان؛ بابت خدمات نمونه؛ دسته: فروش. برای ثبت صریحاً بنویسید: «تأیید و ثبت».';
}

function confirm(action) {
  assert.equal(state.draft.status, 'awaiting_confirmation');
  assert.equal(action, 'تأیید و ثبت', 'only an explicit confirmation may write a record');
  const record = {
    recordId: 'money-001',
    userId: state.draft.userId,
    direction: state.draft.direction,
    amountRaw: state.draft.amountRaw,
    unitRaw: state.draft.unitRaw,
    classification: state.draft.classification,
    purpose: state.draft.purpose,
    sourceFingerprint: state.source.fingerprint,
    status: 'confirmed',
  };
  state.records.push(record);
  state.audit.push({ event: 'money_record_confirmed', recordId: record.recordId, status: 'ok' });
  state.source.body = null; // Synthetic raw source is purged when the draft resolves.
  state.source.status = 'purged_on_confirmation';
  state.draft.status = 'confirmed';
  return 'ثبت شد. شناسهٔ رکورد: money-001';
}

function retrieve(recordId, userId) {
  return state.records.find((record) => record.recordId === recordId && record.userId === userId && record.status === 'confirmed') || null;
}

const transcript = [];
transcript.push(['MESSAGE', syntheticInbound.text]);
transcript.push(['DRAFT + ONE MATERIAL QUESTION', receive(syntheticInbound).join('\n')]);
assert.equal(state.records.length, 0, 'draft/question must not create a record');
transcript.push(['ANSWER', 'فروش']);
transcript.push(['REVISED DRAFT', answerMaterialQuestion('فروش')]);
transcript.push(['EXPLICIT CONFIRMATION', 'تأیید و ثبت']);
transcript.push(['REGISTER', confirm('تأیید و ثبت')]);
const recovered = retrieve('money-001', syntheticInbound.userId);
assert.deepEqual(recovered, {
  recordId: 'money-001',
  userId: 'synthetic-user-001',
  direction: 'incoming',
  amountRaw: '۵۰۰٬۰۰۰',
  unitRaw: 'تومان',
  classification: 'sale',
  purpose: 'خدمات نمونه',
  sourceFingerprint: fingerprint(syntheticInbound.text),
  status: 'confirmed',
});
assert.equal(state.source.body, null, 'raw source must be purged after confirmation');
transcript.push(['RETRIEVE', JSON.stringify(recovered)]);

for (const [stage, detail] of transcript) console.log(`\n[${stage}]\n${detail}`);
console.log('\nPASS: one synthetic record was created only after explicit confirmation; raw source was purged; confirmed record was retrieved.');
