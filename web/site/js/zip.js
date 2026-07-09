/* Minimal ZIP archive reader/writer for PyxelBasic disk images.
 *
 * Pure container logic with no storage knowledge: ui.js turns the storage
 * file list into entries and back. Compression is delegated to the browser's
 * built-in CompressionStream/DecompressionStream ("deflate-raw"), so there is
 * no external dependency; this file only assembles and parses the ZIP
 * container around the deflate streams. The produced archives are ordinary
 * ZIP files (deflate, UTF-8 names via general-purpose bit 11) readable by the
 * standard OS tools, and read() accepts ordinary ZIPs in return (methods
 * "stored" and "deflate" only; no ZIP64, which is far beyond the size of a
 * browser-storage image).
 *
 * Disk images are flat: read() skips directory entries and entries whose
 * names contain a path separator (e.g. macOS __MACOSX/ metadata) and reports
 * them in `skipped` so the UI can mention it.
 */
"use strict";

(function () {
  const LOCAL_SIG = 0x04034b50;
  const CENTRAL_SIG = 0x02014b50;
  const EOCD_SIG = 0x06054b50;
  const FLAG_UTF8 = 0x0800;
  const METHOD_STORED = 0;
  const METHOD_DEFLATE = 8;

  const CRC_TABLE = (() => {
    const t = new Uint32Array(256);
    for (let n = 0; n < 256; n++) {
      let c = n;
      for (let k = 0; k < 8; k++) {
        c = (c & 1) ? (0xedb88320 ^ (c >>> 1)) : (c >>> 1);
      }
      t[n] = c >>> 0;
    }
    return t;
  })();

  function crc32(bytes) {
    let c = 0xffffffff;
    for (let i = 0; i < bytes.length; i++) {
      c = CRC_TABLE[(c ^ bytes[i]) & 0xff] ^ (c >>> 8);
    }
    return (c ^ 0xffffffff) >>> 0;
  }

  async function pipe(bytes, stream) {
    const out = new Blob([bytes]).stream().pipeThrough(stream);
    return new Uint8Array(await new Response(out).arrayBuffer());
  }

  const deflateRaw = (bytes) => pipe(bytes, new CompressionStream("deflate-raw"));
  const inflateRaw = (bytes) => pipe(bytes, new DecompressionStream("deflate-raw"));

  // Local timestamp in the ZIP (MS-DOS) format; 2-second resolution.
  function dosDateTime(d) {
    return {
      date: ((d.getFullYear() - 1980) << 9) | ((d.getMonth() + 1) << 5) | d.getDate(),
      time: (d.getHours() << 11) | (d.getMinutes() << 5) | (d.getSeconds() >> 1),
    };
  }

  const zip = {
    /* build([{name, text}, ...]) -> Blob of a ZIP archive. */
    async build(entries) {
      const enc = new TextEncoder();
      const now = dosDateTime(new Date());
      const chunks = [];
      const central = [];
      let offset = 0;
      for (const { name, text } of entries) {
        const nameBytes = enc.encode(name);
        const data = enc.encode(text);
        const crc = crc32(data);
        const comp = await deflateRaw(data);
        const local = new DataView(new ArrayBuffer(30));
        local.setUint32(0, LOCAL_SIG, true);
        local.setUint16(4, 20, true);            // version needed: 2.0
        local.setUint16(6, FLAG_UTF8, true);
        local.setUint16(8, METHOD_DEFLATE, true);
        local.setUint16(10, now.time, true);
        local.setUint16(12, now.date, true);
        local.setUint32(14, crc, true);
        local.setUint32(18, comp.length, true);
        local.setUint32(22, data.length, true);
        local.setUint16(26, nameBytes.length, true);
        local.setUint16(28, 0, true);            // extra field length
        chunks.push(new Uint8Array(local.buffer), nameBytes, comp);
        central.push({ nameBytes, crc, csize: comp.length, usize: data.length,
                       offset });
        offset += 30 + nameBytes.length + comp.length;
      }
      const cdStart = offset;
      for (const e of central) {
        const cd = new DataView(new ArrayBuffer(46));
        cd.setUint32(0, CENTRAL_SIG, true);
        cd.setUint16(4, 20, true);               // version made by
        cd.setUint16(6, 20, true);               // version needed
        cd.setUint16(8, FLAG_UTF8, true);
        cd.setUint16(10, METHOD_DEFLATE, true);
        cd.setUint16(12, now.time, true);
        cd.setUint16(14, now.date, true);
        cd.setUint32(16, e.crc, true);
        cd.setUint32(20, e.csize, true);
        cd.setUint32(24, e.usize, true);
        cd.setUint16(28, e.nameBytes.length, true);
        // extra/comment lengths, disk number, attributes: all zero
        cd.setUint32(42, e.offset, true);
        chunks.push(new Uint8Array(cd.buffer), e.nameBytes);
        offset += 46 + e.nameBytes.length;
      }
      const eocd = new DataView(new ArrayBuffer(22));
      eocd.setUint32(0, EOCD_SIG, true);
      eocd.setUint16(8, central.length, true);   // entries on this disk
      eocd.setUint16(10, central.length, true);  // entries total
      eocd.setUint32(12, offset - cdStart, true);
      eocd.setUint32(16, cdStart, true);
      chunks.push(new Uint8Array(eocd.buffer));
      return new Blob(chunks, { type: "application/zip" });
    },

    /* read(ArrayBuffer) -> {files: [{name, text}], skipped: [name]}.
       Throws on anything that is not a readable ZIP. */
    async read(buffer) {
      const bytes = new Uint8Array(buffer);
      const view = new DataView(buffer);
      // The EOCD sits at the very end unless the archive has a comment
      // (up to 64 KB); scan backward for the signature.
      let eocd = -1;
      const stop = Math.max(0, bytes.length - 22 - 0xffff);
      for (let i = bytes.length - 22; i >= stop; i--) {
        if (view.getUint32(i, true) === EOCD_SIG) { eocd = i; break; }
      }
      if (eocd < 0) throw new Error("not a ZIP file");
      const count = view.getUint16(eocd + 10, true);
      let pos = view.getUint32(eocd + 16, true);
      const dec = new TextDecoder("utf-8");
      const files = [];
      const skipped = [];
      for (let n = 0; n < count; n++) {
        if (pos + 46 > bytes.length || view.getUint32(pos, true) !== CENTRAL_SIG) {
          throw new Error("broken ZIP central directory");
        }
        const method = view.getUint16(pos + 10, true);
        const crc = view.getUint32(pos + 16, true);
        const csize = view.getUint32(pos + 20, true);
        const nameLen = view.getUint16(pos + 28, true);
        const extraLen = view.getUint16(pos + 30, true);
        const commentLen = view.getUint16(pos + 32, true);
        const localOff = view.getUint32(pos + 42, true);
        const name = dec.decode(bytes.subarray(pos + 46, pos + 46 + nameLen));
        pos += 46 + nameLen + extraLen + commentLen;
        if (name.endsWith("/")) continue;        // directory entry
        if (name.includes("/") || name.includes("\\")) {
          skipped.push(name);
          continue;
        }
        if (localOff + 30 > bytes.length ||
            view.getUint32(localOff, true) !== LOCAL_SIG) {
          throw new Error('broken ZIP entry "' + name + '"');
        }
        // The local header repeats name/extra with its own lengths (the
        // extra field commonly differs from the central one).
        const dataStart = localOff + 30 +
          view.getUint16(localOff + 26, true) +
          view.getUint16(localOff + 28, true);
        const comp = bytes.subarray(dataStart, dataStart + csize);
        let data;
        if (method === METHOD_STORED) {
          data = comp;
        } else if (method === METHOD_DEFLATE) {
          data = await inflateRaw(comp);
        } else {
          throw new Error('unsupported compression (method ' + method +
                          ') for "' + name + '"');
        }
        if (crc32(data) !== crc) {
          throw new Error('corrupt data (CRC mismatch) for "' + name + '"');
        }
        files.push({ name, text: dec.decode(data) });
      }
      return { files, skipped };
    },
  };

  window.pyxelbasicZip = zip;
})();
