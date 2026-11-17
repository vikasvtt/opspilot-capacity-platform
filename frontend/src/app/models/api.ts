export interface User { id: number; email: string; role: 'viewer' | 'engineer' | 'approver'; }
export interface TokenPair { access_token: string; refresh_token: string; token_type: string; }
export interface Site { id: number; name: string; city: string; total_capacity: number; created_at: string; }
export interface Rack { id: number; site_id: number; name: string; total_slots: number; used_slots: number; }
export interface CapacityRequest { id: number; requested_by: number; site_id: number; quantity: number; description: string; status: string; created_at: string; }
export interface Approval { id: number; request_id: number; proposed_by: string; proposal_json: { summary: string; allocations: { rack_id: number; quantity: number }[] }; status: string; created_at: string; }
