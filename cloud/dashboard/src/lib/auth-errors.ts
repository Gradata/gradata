export function friendlyAuthError(message: string): string {
  if (/invalid api key/i.test(message)) {
    return 'Service temporarily unavailable. Please try again in a moment.'
  }
  return message
}
