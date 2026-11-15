// The existing fatal-error policy, evaluated before offering another observation.
export function runtimeErrors(rows) {
  return rows.filter(row => /\[ERROR\]|unobserved task exception|missingmethodexception|method not found|unhandled exception/iu.test(row.line));
}
