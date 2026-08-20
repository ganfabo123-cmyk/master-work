export function trimTrailingSeparators(path: string): string {
  return path.replace(/[\\/]+$/, '')
}

export function joinPath(...parts: string[]): string {
  return parts
    .filter(part => part.length > 0)
    .map((part, index) => {
      if (index === 0) {
        return part.replace(/[\\/]+$/, '')
      }

      return part.replace(/^[\\/]+|[\\/]+$/g, '')
    })
    .filter(part => part.length > 0)
    .join('/')
}
