# Location data and external services

JOBLYFY does not call an external geocoding service. The bundled `static/data/locations.json` is a deliberately small offline catalog. Autocomplete also queries distinct location text on open jobs, so employers can use cities outside the catalog. The catalog's points are approximate **city centers**, never exact employer premises or driving routes.

## Attribution

- Most bundled centers are adapted (rounded to six decimal places or fewer) from [GeoNames' India populated-place catalog](https://www.geonames.org/advanced-search.html?country=IN&featureClass=P&q=&startRow=0), accessed 26 October 2026. Includes Chandigarh, Delhi, Bengaluru, Mumbai, Pune, Hyderabad, Chennai, Kolkata, Jaipur, Ahmedabad, Amritsar, Jalandhar and Dehradun. GeoNames data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/); [GeoNames attribution and data information](https://www.geonames.org/about.html). The application adds a small curated alias set and labels. GeoNames provides data without a warranty of completeness or accuracy.
- Ludhiana (30.90902, 75.85160) and Mohali (30.72, 76.70) reference the corresponding [Ludhiana](https://wiki.openstreetmap.org/wiki/Ludhiana) and [Mohali](https://wiki.openstreetmap.org/wiki/Mohali) OpenStreetMap Wiki location pages, accessed 26 October 2026. Wiki content attribution: OpenStreetMap Wiki contributors, [CC BY-SA 2.0](https://creativecommons.org/licenses/by-sa/2.0/). The adapted catalog is available under CC BY-SA 4.0, retaining these upstream credits; this does not change the licensing of the original project source.
- For Delhi searches, New Delhi is treated as a search alias for the broader Delhi center. This is a product search normalization, not an administrative boundary claim.

## Runtime services

The only optional runtime map is the [OpenStreetMap exported HTML embed](https://wiki.openstreetmap.org/wiki/Export), loaded after the user clicks **Load workplace map**. The address and an ordinary map link remain available. The frame is isolated by the browser and retains OpenStreetMap's built-in controls and attribution; an additional attribution link is visible below it.

[OpenStreetMap copyright / ODbL](https://www.openstreetmap.org/copyright) · [Tile usage policy](https://operations.osmfoundation.org/policies/tiles/).

The application does not download tiles server-side, override tile caching, suppress the map frame's origin referrer, or prefetch maps. OpenStreetMap is best-effort shared infrastructure, not an availability guarantee. Review provider policy and capacity needs before a large deployment.

**Current location:** the browser [Geolocation API](https://developer.mozilla.org/en-US/docs/Web/API/Geolocation/getCurrentPosition) is invoked only by the user action. The site allows geolocation for its own origin only. The browser performs the nearest-catalog-city calculation; precise coordinates are not sent to Django, to maps, to local storage, or to any geocoding service. Outside 50 km of a catalog city, users enter a city manually. Browser permission and a secure context (HTTPS or localhost) are required.
