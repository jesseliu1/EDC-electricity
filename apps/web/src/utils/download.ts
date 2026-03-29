function extractFilename(contentDisposition: string | null, fallbackFilename: string) {
  if (!contentDisposition) {
    return fallbackFilename
  }

  const encodedMatch = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i)
  if (encodedMatch?.[1]) {
    try {
      return decodeURIComponent(encodedMatch[1])
    } catch {
      return encodedMatch[1]
    }
  }

  const plainMatch = contentDisposition.match(/filename="?([^";]+)"?/i)
  if (plainMatch?.[1]) {
    return plainMatch[1]
  }

  return fallbackFilename
}

export async function downloadFile(url: string, fallbackFilename: string) {
  const response = await fetch(url, {
    method: 'GET',
    credentials: 'same-origin'
  })

  if (!response.ok) {
    throw new Error(`download_failed_${response.status}`)
  }

  const fileBlob = await response.blob()
  const objectUrl = window.URL.createObjectURL(fileBlob)
  const link = document.createElement('a')

  link.href = objectUrl
  link.download = extractFilename(response.headers.get('content-disposition'), fallbackFilename)
  link.rel = 'noopener'
  link.style.display = 'none'

  document.body.appendChild(link)
  link.click()
  link.remove()

  window.setTimeout(() => {
    window.URL.revokeObjectURL(objectUrl)
  }, 0)
}
