import React, { useState } from "react";

function safeStringify(obj) {
  try {
    return JSON.stringify(obj, null, 2);
  } catch (e) {
    return String(obj);
  }
}

export default function SanitizedJsonCollapse({ title = "고급/디버그 (sanitized JSON)", data }) {
  const [open, setOpen] = useState(false);

  return (
    <div style={{ marginTop: 12 }}>
      <button className="btn" onClick={() => setOpen(!open)}>
        {open ? "▼" : "▶"} {title}
      </button>
      {open && (
        <pre
          style={{
            marginTop: 8,
            padding: 12,
            background: "#0b1220",
            border: "1px solid #223",
            borderRadius: 8,
            maxHeight: 360,
            overflow: "auto",
            fontSize: 12,
          }}
        >
          {safeStringify(data || {})}
        </pre>
      )}
    </div>
  );
}
