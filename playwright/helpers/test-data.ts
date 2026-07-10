export function timestampName(prefix: string): string {
  return `${prefix}_${Date.now()}`;
}

export function randomPhone(): string {
  const prefixes = ['138', '139', '150', '151', '186', '187', '188', '189'];
  const prefix = prefixes[Math.floor(Math.random() * prefixes.length)];
  const suffix = Math.floor(Math.random() * 100000000).toString().padStart(8, '0');
  return `${prefix}${suffix}`;
}
