import assert from 'node:assert/strict';
import test from 'node:test';
import { baselineComparisons, revenueInference } from './evaluation.js';

const report = (base, actual, winner = 'logistic', n = 10) => ({
  winner, validation: { constant: { brier: base, n: 10 }, [winner]: { brier: actual, n } }
});
test('compares same-population validation errors and direction', () => {
  assert.match(baselineComparisons(report(0.2, 0.15))[0].inference, /25.0% lower.*better/);
  assert.match(baselineComparisons(report(0.2, 0.3))[0].inference, /50.0% higher.*worse/);
});
test('handles missing scores, mismatched samples and zero baseline', () => {
  assert.equal(baselineComparisons({})[0].comparable, false);
  assert.equal(baselineComparisons(report(null, 0))[0].comparable, false);
  assert.equal(baselineComparisons(report(0.2, 0.1, 'logistic', 9))[0].comparable, false);
  assert.match(baselineComparisons(report(0, 0.1))[0].inference, /zero error/);
  assert.match(baselineComparisons(report(0.2, 0.2, 'constant'))[0].inference, /baseline was selected/);
});
test('interprets signed aggregate error without treating missing as zero', () => {
  assert.match(revenueInference({ aggregate_error_pct: -20.41 }), /underestimates.*20.41%/);
  assert.match(revenueInference({ aggregate_error_pct: 5 }), /overestimates.*5.00%/);
  assert.match(revenueInference({ aggregate_error_pct: 0 }), /matches actual/);
  assert.match(revenueInference({ aggregate_error_pct: null }), /unavailable/);
});
