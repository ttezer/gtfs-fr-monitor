import unittest

from gtfs_fr_monitor.regions import dataset_region, region_names, table


def area(kind, code):
    return {"type": kind, "insee": code, "nom": "x"}


class RegionsTest(unittest.TestCase):
    def test_areas(self):
        cases = [
            ([area("commune", "35238")], 53),  # Rennes: Bretagne
            ([area("commune", "2A004")], 94),  # Ajaccio: Corse
            ([area("commune", "97105")], 1),  # Basse-Terre: Guadeloupe ("01")
            ([area("departement", "69")], 84),
            ([area("region", "11")], 11),
            ([area("commune", "35238"), area("departement", "56")], 53),  # both in Bretagne
            ([area("commune", "35238"), area("departement", "69")], None),  # two regions
            ([area("pays", "FR")], None),
            ([area("epci", "000000000")], None),  # unknown
            ([], None),
        ]
        for areas, want in cases:
            with self.subTest(areas=areas):
                self.assertEqual(dataset_region(areas), want)

    def test_epci_across_regions(self):
        multi = next(code for code, rs in table()["epcis"].items() if len(rs) > 1)
        single = next(code for code, rs in table()["epcis"].items() if len(rs) == 1)
        self.assertIsNone(dataset_region([area("epci", multi)]))
        self.assertEqual(dataset_region([area("epci", single)]), int(table()["epcis"][single][0]))

    def test_names(self):
        names = region_names()
        self.assertEqual((len(names), names["11"], names["1"]), (18, "Île-de-France", "Guadeloupe"))


if __name__ == "__main__":
    unittest.main()
