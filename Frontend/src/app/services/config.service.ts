import { HttpClient, HttpHeaders, HttpParams } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { environment } from '../../environments/environment';
import { Observable } from 'rxjs';


@Injectable({
  providedIn: 'root',
})
export class ConfigService {
  data1: any;
  pathParams: any;
  constructor(private http: HttpClient) {}

  get(apiPath: string): Observable<any> {
    return this.http.get<any>(`${environment.apiBaseUrl}${apiPath}`);
  }

  getbyID(apiPath: string, pathParams: string, params?: any): Observable<any> {
    let httpParams = new HttpParams();

    if (params) {
      for (const key in params) {
        if (params.hasOwnProperty(key) && params[key] != null) {
          // Ensure the value is not null or undefined
          httpParams = httpParams.append(key, params[key].toString());
        }
      }
    }

    return this.http.get<any>(`${environment.apiBaseUrl}${apiPath}/${pathParams}`, {
      params: httpParams,
    });
  }
  post(apiPath: string, data: any): Observable<any> {
    return this.http.post<any>(`${environment.apiBaseUrl}${apiPath}`,data);
  }
  //violation report
  postViolation(apiPath: string, data: any): Observable<Blob> {
    const headers = new HttpHeaders({
      'Content-Type': 'application/json',
      'Authorization': 'Token your-auth-token-here' // Replace with your token
    });
    return this.http.post(`${environment.apiBaseUrl}${apiPath}`, data,{ headers, responseType: 'blob' });
  }
  put(apiPath: string, data: any): Observable<any> {
    return this.http.put<any>(`${environment.apiBaseUrl}${apiPath}`, data);
  }
  delete(apiPath: string): Observable<any> {
    return this.http.delete<any>(`${environment.apiBaseUrl}${apiPath}`);
  }
  patch(apiPath: string, data: any): Observable<any> {
    return this.http.patch<any>(`${environment.apiBaseUrl}${apiPath}`, data);
  }
  setData(data: any) {
    this.data1=null;
    this.data1 = data;
  }
  getData() {
    return this.data1;
  }
}
