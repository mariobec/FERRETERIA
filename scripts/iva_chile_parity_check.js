#!/usr/bin/env node
/**
 * Paridad IVA Python ↔ JS. Uso: node scripts/iva_chile_parity_check.js
 * Exit 0 = OK, 1 = mismatch.
 */
'use strict';

const path = require('path');
const iva = require(path.join(__dirname, '..', 'static', 'js', 'offline', 'iva-chile.js'));

const VECTORS = [
  [1190, 1000, 190, 1190],
  [50000, 42017, 7983, 50000],
  [0, 0, 0, 0],
  [1, 1, 0, 1],
  [999, 839, 159, 998],
  [100000, 84034, 15966, 100000],
  [2380, 2000, 380, 2380],
  [5373, 4515, 858, 5373],
];

let failed = 0;
for (const [bruto, expNeto, expIva, expTotal] of VECTORS) {
  const r = iva.desglosarIvaClp(bruto);
  const ok =
    r.neto === expNeto &&
    r.iva === expIva &&
    r.total === expTotal &&
    r.neto + r.iva === r.total &&
    r.iva === iva.ivaDesdeNetoClp(r.neto);
  if (!ok) {
    console.error(
      'FAIL bruto=%s got neto=%s iva=%s total=%s expected %s,%s,%s',
      bruto,
      r.neto,
      r.iva,
      r.total,
      expNeto,
      expIva,
      expTotal
    );
    failed += 1;
  }
}

const sub = iva.subtotalLineaBrutoClp(3, 1990, 10);
if (sub !== 5373) {
  console.error('FAIL subtotalLineaBrutoClp(3,1990,10)=%s expected 5373', sub);
  failed += 1;
}

if (failed) {
  process.exit(1);
}
console.log('iva_chile_parity_check: OK (%s vectors)', VECTORS.length);
process.exit(0);
