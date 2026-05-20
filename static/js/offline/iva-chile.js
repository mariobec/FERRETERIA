/**
 * IVA Chile 19% incluido — paridad con core/domain/shared/iva_chile.py
 * Solo enteros CLP; redondeo ROUND_HALF_UP (no Math.round banker's en cadenas críticas).
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.LhexiaIvaChile = factory();
  }
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  var IVA_TASA = 0.19;
  var IVA_FACTOR = 1.19;

  /**
   * Redondeo half-up a entero para montos positivos.
   * @param {number} value
   * @returns {number}
   */
  function roundHalfUp(value) {
    var v = Number(value);
    if (!isFinite(v) || v <= 0) {
      return 0;
    }
    return Math.floor(v + 0.5);
  }

  /**
   * @param {number} totalBruto CLP bruto (IVA incluido)
   * @returns {{ neto: number, iva: number, total: number }}
   */
  function desglosarIvaClp(totalBruto) {
    var tb = Math.max(0, parseInt(totalBruto, 10) || 0);
    if (tb === 0) {
      return { neto: 0, iva: 0, total: 0 };
    }
    var neto = roundHalfUp(tb / IVA_FACTOR);
    var iva = roundHalfUp(neto * IVA_TASA);
    var total = neto + iva;
    return { neto: neto, iva: iva, total: total };
  }

  /**
   * @param {number} montoNeto
   * @returns {number}
   */
  function ivaDesdeNetoClp(montoNeto) {
    var n = Math.max(0, parseInt(montoNeto, 10) || 0);
    if (n === 0) {
      return 0;
    }
    return roundHalfUp(n * IVA_TASA);
  }

  /**
   * Subtotal línea bruto (precio mostrador × cantidad − descuento %).
   * @param {number} cantidad
   * @param {number|string} precioUnitario
   * @param {number|string} descuentoPct
   * @returns {number}
   */
  function subtotalLineaBrutoClp(cantidad, precioUnitario, descuentoPct) {
    var cant = Math.max(0, parseInt(cantidad, 10) || 0);
    var pu = parseFloat(String(precioUnitario || 0));
    var desc = parseFloat(String(descuentoPct || 0));
    if (!isFinite(pu)) {
      pu = 0;
    }
    if (!isFinite(desc)) {
      desc = 0;
    }
    var val = cant * pu * (1 - desc / 100);
    return Math.max(0, roundHalfUp(val));
  }

  return {
    IVA_TASA: IVA_TASA,
    IVA_FACTOR: IVA_FACTOR,
    roundHalfUp: roundHalfUp,
    desglosarIvaClp: desglosarIvaClp,
    ivaDesdeNetoClp: ivaDesdeNetoClp,
    subtotalLineaBrutoClp: subtotalLineaBrutoClp,
  };
});
