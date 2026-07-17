<?php
/**
 * NeverUpgrade block theme.
 */

if ( ! function_exists( 'neverupgrade_setup' ) ) {
	function neverupgrade_setup() {
		add_theme_support( 'wp-block-styles' );
		add_editor_style( 'style.css' );
	}
}
add_action( 'after_setup_theme', 'neverupgrade_setup' );

function neverupgrade_styles() {
	// The stylesheet is ~3 KB: inlining it removes a render-blocking request,
	// saving one full round trip on slow connections (FCP/LCP win).
	$css = file_get_contents( get_stylesheet_directory() . '/style.css' );
	wp_register_style( 'neverupgrade-style', false, array(), wp_get_theme()->get( 'Version' ) );
	wp_enqueue_style( 'neverupgrade-style' );
	wp_add_inline_style( 'neverupgrade-style', $css );
}
add_action( 'wp_enqueue_scripts', 'neverupgrade_styles' );
