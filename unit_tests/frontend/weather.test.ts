import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { fetchWeatherSummary, WeatherParams } from '../../src/lib/weather';

// Mock the global fetch
const globalFetch = vi.fn();
vi.stubGlobal('fetch', globalFetch);

describe('weather.ts - fetchWeatherSummary', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('constructs the URL with only required parameters', async () => {
    const mockResponse = { condition: 'Sunny', high_c: 25 };
    globalFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    const params: WeatherParams = {
      destinationCity: 'Paris',
      destinationCountry: 'France',
    };

    const result = await fetchWeatherSummary(params);
    
    expect(result).toEqual(mockResponse);
    expect(globalFetch).toHaveBeenCalledTimes(1);
    
    const requestUrl = globalFetch.mock.calls[0][0] as string;
    expect(requestUrl).toContain('destination_city=Paris');
    expect(requestUrl).toContain('destination_country=France');
    expect(requestUrl).not.toContain('start_date');
  });

  it('constructs the URL with all parameters including dates', async () => {
    const mockResponse = { condition: 'Rainy', high_c: 15 };
    globalFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    const params: WeatherParams = {
      destinationCity: 'London',
      destinationCountry: 'UK',
      startDate: '2026-05-10',
      endDate: '2026-05-15',
    };

    await fetchWeatherSummary(params);
    
    const requestUrl = globalFetch.mock.calls[0][0] as string;
    expect(requestUrl).toContain('destination_city=London');
    expect(requestUrl).toContain('destination_country=UK');
    expect(requestUrl).toContain('start_date=2026-05-10');
    expect(requestUrl).toContain('end_date=2026-05-15');
  });

  it('throws an error with the detail message if response is not ok', async () => {
    globalFetch.mockResolvedValueOnce({
      ok: false,
      json: async () => ({ detail: 'Invalid city name' }),
    });

    const params: WeatherParams = {
      destinationCity: 'FakeCity',
      destinationCountry: 'FakeCountry',
    };

    await expect(fetchWeatherSummary(params)).rejects.toThrow('Invalid city name');
  });

  it('throws default error message if json parsing fails on non-ok response', async () => {
    globalFetch.mockResolvedValueOnce({
      ok: false,
      json: async () => { throw new Error('Not JSON'); },
    });

    const params: WeatherParams = {
      destinationCity: 'Paris',
      destinationCountry: 'France',
    };

    await expect(fetchWeatherSummary(params)).rejects.toThrow('Failed to fetch weather data.');
  });
});
