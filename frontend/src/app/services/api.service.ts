import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { Approval, CapacityRequest, Rack, Site } from '../models/api';

@Injectable({providedIn: 'root'})
export class ApiService {
  private readonly base = '/api';
  constructor(private http: HttpClient) {}
  sites(): Promise<Site[]> { return firstValueFrom(this.http.get<Site[]>(`${this.base}/sites`)); }
  racks(): Promise<Rack[]> { return firstValueFrom(this.http.get<Rack[]>(`${this.base}/racks`)); }
  requests(): Promise<CapacityRequest[]> { return firstValueFrom(this.http.get<CapacityRequest[]>(`${this.base}/requests`)); }
  approvals(): Promise<Approval[]> { return firstValueFrom(this.http.get<Approval[]>(`${this.base}/approvals`)); }
  createSite(data: {name: string; city: string; total_capacity: number}): Promise<Site> { return firstValueFrom(this.http.post<Site>(`${this.base}/sites`, data)); }
  createRack(data: {site_id: number; name: string; total_slots: number}): Promise<Rack> { return firstValueFrom(this.http.post<Rack>(`${this.base}/racks`, data)); }
  createRequest(data: {site_id: number; quantity: number; description: string}): Promise<CapacityRequest> { return firstValueFrom(this.http.post<CapacityRequest>(`${this.base}/requests`, data)); }
  propose(id: number): Promise<Approval> { return firstValueFrom(this.http.post<Approval>(`${this.base}/agent/requests/${id}/propose`, {})); }
  review(id: number, decision: 'approve' | 'reject'): Promise<Approval> { return firstValueFrom(this.http.post<Approval>(`${this.base}/approvals/${id}/review`, {decision, reason: decision === 'approve' ? 'Approved after review' : 'Rejected after review'})); }
}
