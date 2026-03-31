from __future__ import annotations

from namera.composer import COMMON_PREFIXES, COMMON_SUFFIXES, ComposerConfig, _dedup, compose


class TestBasicCompose:
    """Test basic keyword + TLD generation."""

    def test_single_keyword_single_tld(self):
        config = ComposerConfig(keywords=["namera"], tlds=["com"])
        result = compose(config)
        assert result == ["namera.com"]

    def test_single_keyword_multiple_tlds(self):
        config = ComposerConfig(keywords=["namera"], tlds=["com", "io"])
        result = compose(config)
        assert result == ["namera.com", "namera.io"]

    def test_multiple_keywords(self):
        config = ComposerConfig(keywords=["foo", "bar"], tlds=["com"])
        result = compose(config)
        assert "foo.com" in result
        assert "bar.com" in result
        assert len(result) == 2


class TestPrefixSuffix:
    """Test prefix/suffix combinations."""

    def test_custom_prefix(self):
        config = ComposerConfig(keywords=["namera"], prefixes=["get"], tlds=["com"])
        result = compose(config)
        assert "getnamera.com" in result
        assert "namera.com" in result  # base keyword always included

    def test_custom_suffix(self):
        config = ComposerConfig(keywords=["namera"], suffixes=["hq"], tlds=["com"])
        result = compose(config)
        assert "namerahq.com" in result
        assert "namera.com" in result

    def test_prefix_and_suffix(self):
        config = ComposerConfig(
            keywords=["namera"], prefixes=["get"], suffixes=["hq"], tlds=["com"]
        )
        result = compose(config)
        assert "namera.com" in result
        assert "getnamera.com" in result
        assert "namerahq.com" in result
        assert "getnamerahq.com" in result
        assert len(result) == 4

    def test_multiple_prefixes_and_suffixes(self):
        config = ComposerConfig(
            keywords=["test"], prefixes=["get", "try"], suffixes=["app", "hq"], tlds=["com"]
        )
        result = compose(config)
        # base + 2 prefix + 2 suffix + 4 prefix*suffix = 9
        assert len(result) == 9
        assert "test.com" in result
        assert "gettest.com" in result
        assert "trytest.com" in result
        assert "testapp.com" in result
        assert "testhq.com" in result
        assert "gettestapp.com" in result
        assert "gettesthq.com" in result
        assert "trytestapp.com" in result
        assert "trytesthq.com" in result


class TestCommonPrefixesSuffixes:
    """Test common prefixes/suffixes inclusion."""

    def test_common_prefixes_flag(self):
        config = ComposerConfig(
            keywords=["namera"], tlds=["com"], use_common_prefixes=True
        )
        result = compose(config)
        # Should include base + all common prefix combos
        assert "namera.com" in result
        for p in COMMON_PREFIXES:
            assert f"{p}namera.com" in result

    def test_common_suffixes_flag(self):
        config = ComposerConfig(
            keywords=["namera"], tlds=["com"], use_common_suffixes=True
        )
        result = compose(config)
        assert "namera.com" in result
        for s in COMMON_SUFFIXES:
            assert f"namera{s}.com" in result

    def test_common_prefixes_merged_with_custom(self):
        config = ComposerConfig(
            keywords=["test"],
            prefixes=["super"],
            tlds=["com"],
            use_common_prefixes=True,
        )
        result = compose(config)
        assert "supertest.com" in result
        assert "gettest.com" in result

    def test_common_suffixes_merged_with_custom(self):
        config = ComposerConfig(
            keywords=["test"],
            suffixes=["zone"],
            tlds=["com"],
            use_common_suffixes=True,
        )
        result = compose(config)
        assert "testzone.com" in result
        assert "testapp.com" in result


class TestDeduplication:
    """Test deduplication behavior."""

    def test_duplicate_keywords_deduped(self):
        config = ComposerConfig(keywords=["foo", "foo"], tlds=["com"])
        result = compose(config)
        assert result.count("foo.com") == 1

    def test_duplicate_prefix_in_custom_and_common(self):
        # "get" is in COMMON_PREFIXES; adding it explicitly shouldn't double it
        config = ComposerConfig(
            keywords=["test"],
            prefixes=["get"],
            tlds=["com"],
            use_common_prefixes=True,
        )
        result = compose(config)
        assert result.count("gettest.com") == 1

    def test_dedup_helper(self):
        assert _dedup(["a", "A", "b", "B", "a"]) == ["a", "b"]

    def test_dedup_strips_whitespace(self):
        assert _dedup(["  a ", "a", " b"]) == ["a", "b"]

    def test_dedup_filters_empty(self):
        assert _dedup(["", " ", "a"]) == ["a"]


class TestMaxLength:
    """Test max_length filtering."""

    def test_max_length_filters_long_labels(self):
        config = ComposerConfig(
            keywords=["abcdefghij"],  # 10 chars
            prefixes=["prefix"],  # 6 chars -> 16 chars total
            tlds=["com"],
            max_length=12,
        )
        result = compose(config)
        assert "abcdefghij.com" in result  # 10 <= 12
        assert "prefixabcdefghij.com" not in result  # 16 > 12

    def test_max_length_63_allows_normal_names(self):
        config = ComposerConfig(keywords=["test"], tlds=["com"])
        result = compose(config)
        assert "test.com" in result

    def test_max_length_exact_boundary(self):
        # Label exactly at max_length should be included
        keyword = "a" * 10
        config = ComposerConfig(keywords=[keyword], tlds=["com"], max_length=10)
        result = compose(config)
        assert f"{keyword}.com" in result

    def test_max_length_one_over(self):
        keyword = "a" * 11
        config = ComposerConfig(keywords=[keyword], tlds=["com"], max_length=10)
        result = compose(config)
        assert len(result) == 0


class TestEmptyKeywords:
    """Test empty keywords handling."""

    def test_empty_keywords_list(self):
        config = ComposerConfig(keywords=[], tlds=["com"])
        result = compose(config)
        assert result == []

    def test_blank_keyword_skipped(self):
        config = ComposerConfig(keywords=["", "  ", "foo"], tlds=["com"])
        result = compose(config)
        assert result == ["foo.com"]

    def test_no_keywords_with_prefixes(self):
        config = ComposerConfig(keywords=[], prefixes=["get"], tlds=["com"])
        result = compose(config)
        assert result == []


class TestSorting:
    """Test that output is sorted."""

    def test_output_sorted_by_label_then_tld(self):
        config = ComposerConfig(keywords=["zebra", "alpha"], tlds=["com", "io"])
        result = compose(config)
        assert result == ["alpha.com", "alpha.io", "zebra.com", "zebra.io"]

    def test_prefixed_names_sorted(self):
        config = ComposerConfig(
            keywords=["test"], prefixes=["z", "a"], tlds=["com"]
        )
        result = compose(config)
        labels = [d.split(".")[0] for d in result]
        assert labels == sorted(labels)

    def test_mixed_sorting(self):
        config = ComposerConfig(
            keywords=["foo"], prefixes=["get"], suffixes=["hq"], tlds=["com"]
        )
        result = compose(config)
        labels = [d.split(".")[0] for d in result]
        assert labels == sorted(labels)


class TestKeywordNormalization:
    """Test that keywords are lowercased and stripped."""

    def test_uppercase_keyword_lowered(self):
        config = ComposerConfig(keywords=["Namera"], tlds=["com"])
        result = compose(config)
        assert "namera.com" in result
        assert "Namera.com" not in result

    def test_whitespace_stripped(self):
        config = ComposerConfig(keywords=["  foo  "], tlds=["com"])
        result = compose(config)
        assert "foo.com" in result
