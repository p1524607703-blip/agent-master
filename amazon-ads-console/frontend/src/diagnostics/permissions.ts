export const canViewDiagnostics = (role?: string | null): boolean =>
  role === 'management' || role === 'super_admin'
