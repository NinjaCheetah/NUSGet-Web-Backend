# NUSGet-Web-Backend
A FastAPI backend used for the server-client version of NUSGet Web, which you can access [here](https://nusget.ninjacheetah.dev) ([source](https://github.com/NinjaCheetah/NUSGet-Web)).

This API offers the ability to download any Wii or DSi title from the Nintendo Update Servers. For free titles (titles that have a common ticket available), you can request a WAD or a ZIP of decypted contents. For all titles, you can request a ZIP of encrypted contents.

The legality of this API is questionable, however it should be noted that the remote server does not store any Nintendo-owned data. All NUS content is downloaded at the time of the request, is manipulated in memory, and is then passed along to the client.

### Endpoints
The NUSGet API uses FastAPI's built-in documentation, so you can view the available endpoints and their parameters [here](https://api.nusget.ninjacheetah.dev/docs).
