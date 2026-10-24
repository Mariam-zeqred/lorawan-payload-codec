// node decoder/test_decoder.js   -- decodes every shared vector and compares with Python's output
var fs = require("fs");
var path = require("path");
var dec = require("./decoder.js");

var vectors = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "tests", "vectors.json"), "utf8"));
var failed = 0, passed = 0;

function hexToBytes(hex) {
  var out = [];
  for (var i = 0; i < hex.length; i += 2) out.push(parseInt(hex.substr(i, 2), 16));
  return out;
}

function check(cond, msg) {
  if (cond) passed++;
  else { failed++; console.log("FAIL " + msg); }
}

var FIELDS = ["temperature_c", "humidity_pct", "battery_v", "door_open", "alarm_code"];
vectors.forEach(function (v) {
  ["compact", "cayenne"].forEach(function (fmt) {
    var r = dec.decodeUplink({ fPort: v[fmt].fport, bytes: hexToBytes(v[fmt].hex) });
    check(r.errors.length === 0 && r.warnings.length === 0, v.name + " " + fmt + ": " + JSON.stringify(r));
    FIELDS.forEach(function (k) {
      check(r.data[k] === v[fmt].decoded[k], v.name + " " + fmt + "." + k + ": " + r.data[k] + " != " + v[fmt].decoded[k]);
    });
    check(JSON.stringify(dec.Decode(v[fmt].fport, hexToBytes(v[fmt].hex))) === JSON.stringify(r.data), "Decode() wrapper");
  });
});

// generic CayenneLPP items and the TTN key style
var g = dec.decodeUplink({ fPort: 2, bytes: hexToBytes("036701100567ffd70673279408880a2736fa0aa70004e2") });
check(g.data.lpp.temperature_3 === 27.2 && g.data.lpp.temperature_5 === -4.1, "reference temperature items");
check(g.data.lpp.barometric_pressure_6 === 1013.2, "barometer");
check(JSON.stringify(g.data.lpp.gps_8) === JSON.stringify({ latitude: 66.5398, longitude: -39.0489, altitude: 12.5 }), "gps 3-byte signed: " + JSON.stringify(g.data.lpp.gps_8));
check(g.warnings.length === 5, "warnings for the five missing node fields: " + g.warnings.length);

// errors
check(dec.decodeUplink({ fPort: 1, bytes: [0x40, 0, 0, 0] }).errors[0].indexOf("5 bytes") >= 0, "short compact");
check(dec.decodeUplink({ fPort: 1, bytes: [0x80, 0, 0, 0, 0] }).errors[0].indexOf("version 2") >= 0, "bad version");
check(dec.decodeUplink({ fPort: 2, bytes: [1, 0x99, 0] }).errors[0].indexOf("0x99") >= 0, "unknown type");
check(dec.decodeUplink({ fPort: 2, bytes: [1, 0x67, 1] }).errors[0].indexOf("truncated temperature") >= 0, "truncated");
check(dec.decodeUplink({ fPort: 3, bytes: [] }).errors[0].indexOf("FPort 3") >= 0, "unknown port");

console.log(passed + " checks passed, " + failed + " failed (" + vectors.length + " vectors)");
process.exit(failed ? 1 : 0);
