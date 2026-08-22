import { Component } from 'react'
import type { ErrorInfo, ReactNode } from 'react'

export class PrintErrorBoundary extends Component<
  { children: ReactNode },
  { hasError: boolean; error: Error | null }
> {
  constructor(props: { children: ReactNode }) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Print rendering error:', error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="print-document bg-nb text-nt p-8">
          <div className="print-chapter border border-nrbr p-6 rounded-lg bg-nrb text-nr">
            <h1 className="text-xl font-bold mb-2">Rendering Error</h1>
            <p className="font-mono text-sm whitespace-pre-wrap">{this.state.error?.message}</p>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
