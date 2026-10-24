// LoRaWAN payload formatter for The Things Stack (v3) and ChirpStack (v4): paste this whole
// file into the console's "Custom JavaScript formatter".  ChirpStack v3's Decode() is wrapped
// at the bottom.  The layouts mirror src/lorawan_payload_codec/{compact,cayenne,frames}.py and
// lib/payload_codec; decoder/test_decoder.js checks every shared vector against Python's output.
//
//   FPort 1  compact, 5 bytes       -> data.{temperature_c, humidity_pct, battery_v, door_open, alarm_code}
//   FPort 2  CayenneLPP, any length -> the same five node fields (channels 1..5) + data.lpp with
//                                      every item as TTN's built-in decoder names them.

var COMPACT_VERSION = 1;
var CH = { temperature: 1, humidity: 2, battery: 3, door: 4, alarm: 5 };

// CayenneLPP type table: [name, [[field, bytes, signed, divisor], ...]]
var LPP_TYPES = {
  0x00: ["digital_in", [["value", 1, false, 1]]],
  0x01: ["digital_out", [["value", 1, false, 1]]],
  0x02: ["analog_in", [["value", 2, true, 100]]],
  0x03: ["analog_out", [["value", 2, true, 100]]],
  0x65: ["luminosity", [["value", 2, false, 1]]],
  0x66: ["presence", [["value", 1, false, 1]]],
  0x67: ["temperature", [["value", 2, true, 10]]],
  0x68: ["relative_humidity", [["value", 1, false, 2]]],
  0x71: ["accelerometer", [["x", 2, true, 1000], ["y", 2, true, 1000], ["z", 2, true, 1000]]],
  0x73: ["barometric_pressure", [["value", 2, false, 10]]],
  0x86: ["gyrometer", [["x", 2, true, 100], ["y", 2, true, 100], ["z", 2, true, 100]]],
  0x88: ["gps", [["latitude", 3, true, 10000], ["longitude", 3, true, 10000], ["altitude", 3, true, 100]]],
};

function readInt(bytes, offset, size, signed) {
  var v = 0;
  for (var i = 0; i < size; i++) v = v * 256 + bytes[offset + i];
  if (signed && v >= Math.pow(2, 8 * size - 1)) v -= Math.pow(2, 8 * size);
  return v;
}

function decodeCompact(bytes) {
  if (bytes.length !== 5) return { errors: ["compact frame is 5 bytes, got " + bytes.length] };
  var version = bytes[0] >> 6;
  if (version !== COMPACT_VERSION) return { errors: ["unsupported compact frame version " + version] };
  return {
    data: {
      temperature_c: readInt(bytes, 1, 2, true) / 100,
      humidity_pct: bytes[3] / 2,
      battery_v: (2000 + bytes[4] * 10) / 1000,
      door_open: (bytes[0] & 0x20) !== 0,
      alarm_code: bytes[0] & 0x1f,
    },
  };
}

function decodeCayenne(bytes) {
  var lpp = {};
  var i = 0;
  while (i < bytes.length) {
    if (i + 2 > bytes.length) return { errors: ["truncated item header at byte " + i] };
    var channel = bytes[i], type = LPP_TYPES[bytes[i + 1]];
    if (!type) return { errors: ["unknown CayenneLPP type 0x" + bytes[i + 1].toString(16) + " at byte " + (i + 1)] };
    i += 2;
    var fields = type[1], values = {};
    for (var f = 0; f < fields.length; f++) {
      var size = fields[f][1];
      if (i + size > bytes.length) return { errors: ["truncated " + type[0] + " data at byte " + i] };
      values[fields[f][0]] = readInt(bytes, i, size, fields[f][2]) / fields[f][3];
      i += size;
    }
    lpp[type[0] + "_" + channel] = fields.length === 1 ? values.value : values;
  }
  var data = { lpp: lpp }, warnings = [];
  var want = {
    temperature_c: "temperature_" + CH.temperature,
    humidity_pct: "relative_humidity_" + CH.humidity,
    battery_v: "analog_in_" + CH.battery,
    door_open: "digital_in_" + CH.door,
    alarm_code: "digital_in_" + CH.alarm,
  };
  for (var key in want) {
    if (lpp[want[key]] === undefined) warnings.push("frame lacks " + want[key]);
    else data[key] = key === "door_open" ? lpp[want[key]] !== 0 : lpp[want[key]];
  }
  return { data: data, warnings: warnings };
}

function decodeUplink(input) {
  var out;
  if (input.fPort === 1) out = decodeCompact(input.bytes);
  else if (input.fPort === 2) out = decodeCayenne(input.bytes);
  else out = { errors: ["no decoder for FPort " + input.fPort] };
  return { data: out.data || {}, warnings: out.warnings || [], errors: out.errors || [] };
}

// ChirpStack v3 signature
function Decode(fPort, bytes) {
  return decodeUplink({ fPort: fPort, bytes: bytes }).data;
}

if (typeof module !== "undefined") module.exports = { decodeUplink: decodeUplink, Decode: Decode };
