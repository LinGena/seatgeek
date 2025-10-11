from proxies.get_proxies import update_proxies
from db.core import IsDbTable
from parser.get_tickets import GetTickets
from parser.get_events import GetEvents

def main():
    pass



if __name__ == "__main__":
    # IsDbTable().check()
    # update_proxies()
    # GetEvents().get()
    GetTickets().get()
    # main()
