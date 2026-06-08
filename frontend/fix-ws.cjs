const fs = require('fs');
const path = require('path');

const filePath = path.join(__dirname, 'src', 'api', 'endpoints.ts');
let content = fs.readFileSync(filePath, 'utf8');

if (content.includes('createBatchWebSocket')) {
  console.log('Already exists');
  process.exit(0);
}

const wsFunction = `\r\n\r\nexport function createBatchWebSocket(batchId: string): WebSocket {\r\n  const baseUrl = import.meta.env.VITE_API_BASE_URL || '/api/v1';\r\n  if (baseUrl.startsWith('/')) {\r\n    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';\r\n    return new WebSocket(\`\${protocol}//\${window.location.host}\${baseUrl}/batch/\${batchId}/ws\`);\r\n  }\r\n  const wsBase = baseUrl.replace(/^http/, 'ws');\r\n  return new WebSocket(\`\${wsBase}/batch/\${batchId}/ws\`);\r\n}\r\n`;

// Insert after createBatchLogStream function
const marker = "return new EventSource(`${baseUrl}/batch/${batchId}/logs`);\r\n}";
if (content.includes(marker)) {
  content = content.replace(marker, marker + wsFunction);
  fs.writeFileSync(filePath, content);
  console.log('Added createBatchWebSocket');
} else {
  console.log('Could not find insertion point');
}
