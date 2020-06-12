/*******************************************************************************
 * Copyright (c) 2020 Haonan Huang.
 *
 *     This file is part of QuantumVITAS (Quantum Visualization Interactive 
 *     Toolkit for Ab-initio Simulations).
 *
 *     QuantumVITAS is free software: you can redistribute it and/or modify
 *     it under the terms of the GNU General Public License as published by
 *     the Free Software Foundation, either version 3 of the License, or any 
 *     later version.
 *
 *     QuantumVITAS is distributed in the hope that it will be useful,
 *     but WITHOUT ANY WARRANTY; without even the implied warranty of
 *     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *     GNU General Public License for more details.
 *
 *     You should have received a copy of the GNU General Public License
 *     along with QuantumVITAS.  If not, see <https://www.gnu.org/licenses/gpl-3.0.txt>.
 *******************************************************************************/
package main.java.com.pseudopot;

public class SSSPEnum {
	private SSSPEnum() {
	}
	public static enum Efficiency {
		//SSSP library for pseudopotential files
		//SSSP Efficiency (version 1.1)
		//For licenses and acknowledgments please go to the website below
		//https://www.materialscloud.org/discover/sssp/table/efficiency
		
		Ag("SSSP_efficiency",50.0,4.0,"Ag_ONCV_PBE-1.0.oncvpsp.upf","94f47bd0669c641108e45594df92fabc","SG15",200.0),
		Al("SSSP_efficiency",30.0,8.0,"Al.pbe-n-kjpaw_psl.1.0.0.UPF","cfc449ca30b5f3223ec38ddd88ac046d","100PAW",240.0),
		Ar("SSSP_efficiency",60.0,4.0,"Ar_ONCV_PBE-1.1.oncvpsp.upf","46d28409cdd246843f76b7675277a949","SG15-1.1",240.0),
		As("SSSP_efficiency",35.0,8.0,"As.pbe-n-rrkjus_psl.0.2.UPF","767315de957beeeb34f87d97bf945c8f","031US",280.0),
		Au("SSSP_efficiency",45.0,4.0,"Au_ONCV_PBE-1.0.oncvpsp.upf","d14007822ba0e19f0206237467fc06c2","SG15",180.0),
		B("SSSP_efficiency",35.0,8.0,"b_pbe_v1.4.uspp.F.UPF","cc6de2960df11db49a60e589f9ebb39b","GBRV-1.4",280.0),
		Ba("SSSP_efficiency",30.0,8.0,"Ba.pbe-spn-kjpaw_psl.1.0.0.UPF","c432291d3e53af55f19d5e8866385beb","100PAW",240.0),
		Be("SSSP_efficiency",40.0,8.0,"be_pbe_v1.4.uspp.F.UPF","5ecff1440924c7c98ad504bef30f5264","GBRV-1.4",320.0),
		Bi("SSSP_efficiency",45.0,8.0,"Bi_pbe_v1.uspp.F.UPF","cceb9f28ec65b6d7ff33140f5b0b1758","GBRV-1.2",360.0),
		Br("SSSP_efficiency",30.0,8.0,"br_pbe_v1.4.uspp.F.UPF","d3ffb7b29f6225aa16fe06858fb2a80b","GBRV-1.4",240.0),
		C("SSSP_efficiency",45.0,8.0,"C.pbe-n-kjpaw_psl.1.0.0.UPF","5d2aebdfa2cae82b50a7e79e9516da0f","100PAW",360.0),
		Ca("SSSP_efficiency",30.0,8.0,"Ca_pbe_v1.uspp.F.UPF","403a4c14b9e4d4dfdc3024c9a3812218","GBRV-1.2",240.0),
		Cd("SSSP_efficiency",60.0,8.0,"Cd.pbe-dn-rrkjus_psl.0.3.1.UPF","558e9f355611b531a870a69ef6ace9e2","031US",480.0),
		Ce("SSSP_efficiency",40.0,8.0,"Ce.GGA-PBE-paw-v1.0.UPF","c46c5ce91c1b1c29a1e5d4b97f9db5f7","Wentzcovitch",320.0),
		Cl("SSSP_efficiency",40.0,8.0,"cl_pbe_v1.4.uspp.F.UPF","fc6f6913ecf08c9257cb748ef0700058","GBRV-1.4",320.0),
		Co("SSSP_efficiency",45.0,8.0,"Co_pbe_v1.2.uspp.F.UPF","5f91765df6ddd3222702df6e7b74a16d","GBRV-1.2",360.0),
		Cr("SSSP_efficiency",40.0,8.0,"cr_pbe_v1.5.uspp.F.UPF","0d52af634a40206e4dee301ad30da4bf","GBRV-1.5",320.0),
		Cs("SSSP_efficiency",30.0,8.0,"Cs_pbe_v1.uspp.F.UPF","3476d69cb178dfad3ffaa59df4e07ca4","GBRV-1.2",240.0),
		Cu("SSSP_efficiency",55.0,8.0,"Cu_pbe_v1.2.uspp.F.UPF","6e991ff952a84172a2a52a1c1e996048","GBRV-1.2",440.0),
		Dy("SSSP_efficiency",40.0,8.0,"Dy.GGA-PBE-paw-v1.0.UPF","aaa222e85efa51d78e19b07c890454ab","Wentzcovitch",320.0),
		Er("SSSP_efficiency",40.0,8.0,"Er.GGA-PBE-paw-v1.0.UPF","b08ffd41d90ff95dc07468a56b1546b7","Wentzcovitch",320.0),
		Eu("SSSP_efficiency",40.0,8.0,"Eu.GGA-PBE-paw-v1.0.UPF","2f98cd20d76ba534504868fe92c99950","Wentzcovitch",320.0),
		F("SSSP_efficiency",45.0,8.0,"f_pbe_v1.4.uspp.F.UPF","4c38b6a325caf53ec0e86aed9459de46","GBRV-1.4",360.0),
		Fe("SSSP_efficiency",90.0,12.0,"Fe.pbe-spn-kjpaw_psl.0.2.1.UPF","e86618425769142926afa95317d90200","031PAW",1080.0),
		Ga("SSSP_efficiency",70.0,8.0,"Ga.pbe-dn-kjpaw_psl.1.0.0.UPF","a27b4342b1af7e5f338de752e9ed7044","100PAW",560.0),
		Gd("SSSP_efficiency",40.0,8.0,"Gd.GGA-PBE-paw-v1.0.UPF","5be61ee804628d0d4564e5bf0c6b2d4d","Wentzcovitch",320.0),
		Ge("SSSP_efficiency",40.0,8.0,"ge_pbe_v1.4.uspp.F.UPF","9c9eaa91e581c3f09632fb3098b2c6b2","GBRV-1.4",320.0),
		H("SSSP_efficiency",60.0,8.0,"H.pbe-rrkjus_psl.1.0.0.UPF","f52b6d4d1c606e5624b1dc7b2218f220","100US",480.0),
		He("SSSP_efficiency",50.0,4.0,"He_ONCV_PBE-1.0.oncvpsp.upf","e7160162b946020f132a727efeb32d00","SG15",200.0),
		Hf("SSSP_efficiency",50.0,4.0,"Hf-sp.oncvpsp.upf","417ed15784afe83d2e06dacf143de3f8","Dojo",200.0),
		Hg("SSSP_efficiency",50.0,4.0,"Hg_ONCV_PBE-1.0.oncvpsp.upf","dd5a8773074bfcf4280086d4d95875c4","SG15",200.0),
		Ho("SSSP_efficiency",40.0,8.0,"Ho.GGA-PBE-paw-v1.0.UPF","180317b7bae2d95653b620b8c21968ce","Wentzcovitch",320.0),
		I("SSSP_efficiency",35.0,8.0,"I.pbe-n-kjpaw_psl.0.2.UPF","d4ef18d9c8f18dc85e5843bca1e50dc0","031PAW",280.0),
		In("SSSP_efficiency",50.0,8.0,"In.pbe-dn-rrkjus_psl.0.2.2.UPF","25e7c42c3b55b68f4bf926be2e7201a4","031US",400.0),
		Ir("SSSP_efficiency",55.0,8.0,"Ir_pbe_v1.2.uspp.F.UPF","8836f839c3459d2b385c504ce6d91f2c","GBRV-1.2",440.0),
		K("SSSP_efficiency",60.0,8.0,"K.pbe-spn-kjpaw_psl.1.0.0.UPF","7d58810084cac21f60fbe77ea2b688fd","100PAW",480.0),
		Kr("SSSP_efficiency",45.0,4.0,"Kr_ONCV_PBE-1.0.oncvpsp.upf","f2280ecf57a6c8a47e066f0532d843fa","SG15",180.0),
		La("SSSP_efficiency",40.0,8.0,"La.GGA-PBE-paw-v1.0.UPF","9bc570786a79c122988210fab848eb7f","Wentzcovitch",320.0),
		Li("SSSP_efficiency",40.0,8.0,"li_pbe_v1.4.uspp.F.UPF","e912e257baa3777c20ea3d68f190483c","GBRV-1.4",320.0),
		Lu("SSSP_efficiency",45.0,8.0,"Lu.GGA-PBE-paw-v1.0.UPF","cc59902dbb0747cc98260d4f1c8f461e","Wentzcovitch",360.0),
		Mg("SSSP_efficiency",30.0,8.0,"Mg.pbe-n-kjpaw_psl.0.3.0.UPF","24ecedc7f3e3cbe212e682f4413594e4","031PAW",240.0),
		Mn("SSSP_efficiency",65.0,12.0,"mn_pbe_v1.5.uspp.F.UPF","82ef2b46521d7a7d9e736dc3972e4928","GBRV-1.5",780.0),
		Mo("SSSP_efficiency",35.0,4.0,"Mo_ONCV_PBE-1.0.oncvpsp.upf","1b5d28e075c9ccadda658a603575cd1f","SG15",140.0),
		N("SSSP_efficiency",60.0,8.0,"N.pbe-n-radius_5.UPF","16739722b17309cd8fe442a2ace49922","THEOS",480.0),
		Na("SSSP_efficiency",40.0,8.0,"na_pbe_v1.5.uspp.F.UPF","44600605ef58000f06b90626533354dc","GBRV-1.5",320.0),
		Nb("SSSP_efficiency",40.0,8.0,"Nb.pbe-spn-kjpaw_psl.0.3.0.UPF","411d72ad547312f8017e2943ceca08cc","031PAW",320.0),
		Nd("SSSP_efficiency",40.0,8.0,"Nd.GGA-PBE-paw-v1.0.UPF","6ed08d5e4060cc1ad99b3d24ba8e637d","Wentzcovitch",320.0),
		Ne("SSSP_efficiency",50.0,4.0,"Ne_ONCV_PBE-1.0.oncvpsp.upf","9b5acc4cb48b9d80e669eadd528e4e8f","SG15",200.0),
		Ni("SSSP_efficiency",45.0,8.0,"ni_pbe_v1.4.uspp.F.UPF","1ee80287db30b12d2bc1f57a5b5d6409","GBRV-1.4",360.0),
		O("SSSP_efficiency",50.0,8.0,"O.pbe-n-kjpaw_psl.0.1.UPF","0234752ac141de4415c5fc33072bef88","031PAW",400.0),
		Os("SSSP_efficiency",40.0,8.0,"Os_pbe_v1.2.uspp.F.UPF","a3fb40a04f0c37c25c34bbc47164c9a8","GBRV-1.2",320.0),
		P("SSSP_efficiency",30.0,8.0,"P.pbe-n-rrkjus_psl.1.0.0.UPF","8b930f418f0a4573dca56cd030ffe088","100US",240.0),
		Pb("SSSP_efficiency",40.0,8.0,"Pb.pbe-dn-kjpaw_psl.0.2.2.UPF","9d431e6316058b74ade52399a6cf67da","031PAW",320.0),
		Pd("SSSP_efficiency",45.0,4.0,"Pd_ONCV_PBE-1.0.oncvpsp.upf","eb77f42b51d86fb18e25f68156a31cf1","SG15",180.0),
		Pm("SSSP_efficiency",40.0,8.0,"Pm.GGA-PBE-paw-v1.0.UPF","19bca56110d8480befcb833617dbc7df","Wentzcovitch",320.0),
		Po("SSSP_efficiency",75.0,8.0,"Po.pbe-dn-rrkjus_psl.1.0.0.UPF","3f8a5a8b7a531f42ca8381c21d3cd528","100US",600.0),
		Pr("SSSP_efficiency",40.0,8.0,"Pr.GGA-PBE-paw-v1.0.UPF","8bd2f9d65236044fbf839895b9bd72c8","Wentzcovitch",320.0),
		Pt("SSSP_efficiency",35.0,8.0,"pt_pbe_v1.4.uspp.F.UPF","f09d6de1a584b5a045c4fc126da2d0c4","GBRV-1.4",280.0),
		Rb("SSSP_efficiency",30.0,4.0,"Rb_ONCV_PBE-1.0.oncvpsp.upf","55a5172d6bfbce6759a58e35d43f6aa9","SG15",120.0),
		Re("SSSP_efficiency",30.0,8.0,"Re_pbe_v1.2.uspp.F.UPF","85f993410f3e006da9d71c142b4ad953","GBRV-1.2",240.0),
		Rh("SSSP_efficiency",35.0,4.0,"Rh_ONCV_PBE-1.0.oncvpsp.upf","ba07c69523b14cacd10683cd4c4284c1","SG15",140.0),
		Rn("SSSP_efficiency",120.0,8.0,"Rn.pbe-dn-kjpaw_psl.1.0.0.UPF","03f6b960ab99273412830d0b4aa01365","100PAW",960.0),
		Ru("SSSP_efficiency",35.0,4.0,"Ru_ONCV_PBE-1.0.oncvpsp.upf","be037bb81c227cfb9b1461a9f099f4bd","SG15",140.0),
		S("SSSP_efficiency",35.0,8.0,"s_pbe_v1.4.uspp.F.UPF","88d86576ff6df21479756cfb9bdac1df","GBRV-1.4",280.0),
		Sb("SSSP_efficiency",40.0,8.0,"sb_pbe_v1.4.uspp.F.UPF","9bc50dfb53373b713f5709b9110fe27f","GBRV-1.4",320.0),
		Sc("SSSP_efficiency",40.0,4.0,"Sc_ONCV_PBE-1.0.oncvpsp.upf","e21af8023abb52e52cb7cd3133e4a229","SG15",160.0),
		Se("SSSP_efficiency",30.0,8.0,"Se_pbe_v1.uspp.F.UPF","1b3568f3a8ae88f9a2a0ad0698632c85","GBRV-1.2",240.0),
		Si("SSSP_efficiency",30.0,8.0,"Si.pbe-n-rrkjus_psl.1.0.0.UPF","0b0bb1205258b0d07b9f9672cf965d36","100US",240.0),
		Sm("SSSP_efficiency",40.0,8.0,"Sm.GGA-PBE-paw-v1.0.UPF","3ddcafad514a6ea7d14a52e8ca30603a","Wentzcovitch",320.0),
		Sn("SSSP_efficiency",60.0,8.0,"Sn_pbe_v1.uspp.F.UPF","4cf58ce39ec5d5d420df3dd08604eb00","GBRV-1.2",480.0),
		Sr("SSSP_efficiency",30.0,8.0,"Sr_pbe_v1.uspp.F.UPF","6b418c05fbe9db5448babca5e47b7a5b","GBRV-1.2",240.0),
		Ta("SSSP_efficiency",45.0,8.0,"Ta_pbe_v1.uspp.F.UPF","f8bbe9446314a3b8ea5d9f3e3836c939","GBRV-1.2",360.0),
		Tb("SSSP_efficiency",40.0,8.0,"Tb.GGA-PBE-paw-v1.0.UPF","37cc37188d4ce4bd414f4b03d8f3cab6","Wentzcovitch",320.0),
		Tc("SSSP_efficiency",30.0,4.0,"Tc_ONCV_PBE-1.0.oncvpsp.upf","1c2b1e6c8b361b656073c0c20ed4f60a","SG15",120.0),
		Te("SSSP_efficiency",30.0,8.0,"Te_pbe_v1.uspp.F.UPF","c319670d6894cc26e93307826a071b75","GBRV-1.2",240.0),
		Ti("SSSP_efficiency",35.0,8.0,"ti_pbe_v1.4.uspp.F.UPF","88a00a6731bd790ddea75d31a80cb452","GBRV-1.4",280.0),
		Tl("SSSP_efficiency",50.0,8.0,"Tl_pbe_v1.2.uspp.F.UPF","b76cf1f7e72655a2b2c53cf6385d7059","GBRV-1.2",400.0),
		Tm("SSSP_efficiency",40.0,8.0,"Tm.GGA-PBE-paw-v1.0.UPF","5bf2bc9b2000dc366ce20ce5239c3999","Wentzcovitch",320.0),
		V("SSSP_efficiency",35.0,8.0,"v_pbe_v1.4.uspp.F.UPF","22b79981416ebb76fdaf5b1b8640f6fb","GBRV-1.4",280.0),
		W("SSSP_efficiency",30.0,8.0,"W_pbe_v1.2.uspp.F.UPF","9c083fa34c2a2ea0f02f1f893e16e1c8","GBRV-1.2",240.0),
		Xe("SSSP_efficiency",60.0,4.0,"Xe_ONCV_PBE-1.1.oncvpsp.upf","f6ea899d5a535d3f5731d9e48edfe3e3","SG15-1.1",240.0),
		Y("SSSP_efficiency",35.0,8.0,"Y_pbe_v1.uspp.F.UPF","2cf71db95cafeb975fc457bd7f14888e","GBRV-1.2",280.0),
		Yb("SSSP_efficiency",40.0,8.0,"Yb.GGA-PBE-paw-v1.0.UPF","c46ad346ad0f6b1727467da500789f7b","Wentzcovitch",320.0),
		Zn("SSSP_efficiency",40.0,8.0,"Zn_pbe_v1.uspp.F.UPF","df62231357ef9e81f77b2b3087fa5675","GBRV-1.2",320.0),
		Zr("SSSP_efficiency",30.0,8.0,"Zr_pbe_v1.uspp.F.UPF","5db81b1e868ab7776c4564c113de050b","GBRV-1.2",240.0)
		;

		private final String folderName;
		private final double ecutwfc;//Ry
		private final double dual;
		private final String fileName;
		private final String md5Str;
		private final String ppType;
		private final double ecutrho;//Ry

	    private Efficiency(String folderName, double ecutwfc, double dual, String fileName, String md5Str, String ppType, double ecutrho) {
	    	this.folderName = folderName;
	    	this.ecutwfc = ecutwfc;
	    	this.dual = dual;
	    	this.fileName = fileName;
	    	this.md5Str = md5Str;
	    	this.ppType = ppType;
	    	this.ecutrho = ecutrho;
	    }

	    public double getEcutwfc() {return ecutwfc;}
		public double getDual() {return dual;}
		public String getFileName() {return fileName;}//necessary
		public String getMd5Str() {return md5Str;}
		public String getPpType() {return ppType;}
		public double getEcutrho() {return ecutrho;}
		public String getFolderName() {return folderName;}//necessary
	}
	
	public static enum Precision {
		//SSSP library for pseudopotential files
		//SSSP Precision (version 1.1)
		//For licenses and acknowledgments please go to the website below
		//https://www.materialscloud.org/discover/sssp/table/precision
		
		Ag("SSSP_precision",55.0,4.0,"Ag_ONCV_PBE-1.0.oncvpsp.upf","94f47bd0669c641108e45594df92fabc","SG15",220.0),
		Al("SSSP_precision",30.0,8.0,"Al.pbe-n-kjpaw_psl.1.0.0.UPF","cfc449ca30b5f3223ec38ddd88ac046d","100PAW",240.0),
		Ar("SSSP_precision",120.0,4.0,"Ar_ONCV_PBE-1.1.oncvpsp.upf","46d28409cdd246843f76b7675277a949","SG15-1.1",480.0),
		As("SSSP_precision",35.0,8.0,"As.pbe-n-rrkjus_psl.0.2.UPF","767315de957beeeb34f87d97bf945c8f","031US",280.0),
		Au("SSSP_precision",50.0,4.0,"Au_ONCV_PBE-1.0.oncvpsp.upf","d14007822ba0e19f0206237467fc06c2","SG15",200.0),
		B("SSSP_precision",55.0,8.0,"B_pbe_v1.01.uspp.F.UPF","d081ebb89d0c768e112975f650467a00","GBRV-1.2",440.0),
		Ba("SSSP_precision",35.0,8.0,"Ba.pbe-spn-kjpaw_psl.1.0.0.UPF","c432291d3e53af55f19d5e8866385beb","100PAW",280.0),
		Be("SSSP_precision",55.0,4.0,"Be_ONCV_PBE-1.0.oncvpsp.upf","28b8ff6b8130143f4fef2c47cbef089d","SG15",220.0),
		Bi("SSSP_precision",50.0,8.0,"Bi_pbe_v1.uspp.F.UPF","cceb9f28ec65b6d7ff33140f5b0b1758","GBRV-1.2",400.0),
		Br("SSSP_precision",90.0,8.0,"br_pbe_v1.4.uspp.F.UPF","d3ffb7b29f6225aa16fe06858fb2a80b","GBRV-1.4",720.0),
		C("SSSP_precision",45.0,8.0,"C.pbe-n-kjpaw_psl.1.0.0.UPF","5d2aebdfa2cae82b50a7e79e9516da0f","100PAW",360.0),
		Ca("SSSP_precision",30.0,8.0,"Ca_pbe_v1.uspp.F.UPF","403a4c14b9e4d4dfdc3024c9a3812218","GBRV-1.2",240.0),
		Cd("SSSP_precision",90.0,8.0,"Cd.pbe-dn-rrkjus_psl.0.3.1.UPF","558e9f355611b531a870a69ef6ace9e2","031US",720.0),
		Ce("SSSP_precision",50.0,8.0,"Ce.GGA-PBE-paw-v1.0.UPF","c46c5ce91c1b1c29a1e5d4b97f9db5f7","Wentzcovitch",400.0),
		Cl("SSSP_precision",100.0,8.0,"Cl.pbe-n-rrkjus_psl.1.0.0.UPF","18cc83b4be324290a879bee3176034ba","100US",800.0),
		Co("SSSP_precision",90.0,12.0,"Co_pbe_v1.2.uspp.F.UPF","5f91765df6ddd3222702df6e7b74a16d","GBRV-1.2",1080.0),
		Cr("SSSP_precision",40.0,8.0,"cr_pbe_v1.5.uspp.F.UPF","0d52af634a40206e4dee301ad30da4bf","GBRV-1.5",320.0),
		Cs("SSSP_precision",30.0,8.0,"Cs_pbe_v1.uspp.F.UPF","3476d69cb178dfad3ffaa59df4e07ca4","GBRV-1.2",240.0),
		Cu("SSSP_precision",90.0,4.0,"Cu_ONCV_PBE-1.0.oncvpsp.upf","695ac441eccbb634fec39edbf1c7156d","SG15",360.0),
		Dy("SSSP_precision",40.0,8.0,"Dy.GGA-PBE-paw-v1.0.UPF","aaa222e85efa51d78e19b07c890454ab","Wentzcovitch",320.0),
		Er("SSSP_precision",40.0,8.0,"Er.GGA-PBE-paw-v1.0.UPF","b08ffd41d90ff95dc07468a56b1546b7","Wentzcovitch",320.0),
		Eu("SSSP_precision",40.0,8.0,"Eu.GGA-PBE-paw-v1.0.UPF","2f98cd20d76ba534504868fe92c99950","Wentzcovitch",320.0),
		F("SSSP_precision",90.0,4.0,"F.oncvpsp.upf","dbf8367619a749999a0442b33b80a7e7","Dojo",360.0),
		Fe("SSSP_precision",90.0,12.0,"Fe.pbe-spn-kjpaw_psl.0.2.1.UPF","e86618425769142926afa95317d90200","031PAW",1080.0),
		Ga("SSSP_precision",90.0,8.0,"Ga.pbe-dn-kjpaw_psl.1.0.0.UPF","a27b4342b1af7e5f338de752e9ed7044","100PAW",720.0),
		Gd("SSSP_precision",40.0,8.0,"Gd.GGA-PBE-paw-v1.0.UPF","5be61ee804628d0d4564e5bf0c6b2d4d","Wentzcovitch",320.0),
		Ge("SSSP_precision",45.0,8.0,"ge_pbe_v1.4.uspp.F.UPF","9c9eaa91e581c3f09632fb3098b2c6b2","GBRV-1.4",360.0),
		H("SSSP_precision",80.0,4.0,"H_ONCV_PBE-1.0.oncvpsp.upf","1790becc920ee074925cf490c71280fe","SG15",320.0),
		He("SSSP_precision",55.0,4.0,"He_ONCV_PBE-1.0.oncvpsp.upf","e7160162b946020f132a727efeb32d00","SG15",220.0),
		Hf("SSSP_precision",55.0,4.0,"Hf-sp.oncvpsp.upf","417ed15784afe83d2e06dacf143de3f8","Dojo",220.0),
		Hg("SSSP_precision",55.0,4.0,"Hg_ONCV_PBE-1.0.oncvpsp.upf","dd5a8773074bfcf4280086d4d95875c4","SG15",220.0),
		Ho("SSSP_precision",40.0,8.0,"Ho.GGA-PBE-paw-v1.0.UPF","180317b7bae2d95653b620b8c21968ce","Wentzcovitch",320.0),
		I("SSSP_precision",45.0,8.0,"I.pbe-n-kjpaw_psl.0.2.UPF","d4ef18d9c8f18dc85e5843bca1e50dc0","031PAW",360.0),
		In("SSSP_precision",50.0,8.0,"In.pbe-dn-rrkjus_psl.0.2.2.UPF","25e7c42c3b55b68f4bf926be2e7201a4","031US",400.0),
		Ir("SSSP_precision",65.0,8.0,"Ir_pbe_v1.2.uspp.F.UPF","8836f839c3459d2b385c504ce6d91f2c","GBRV-1.2",520.0),
		K("SSSP_precision",60.0,8.0,"K.pbe-spn-kjpaw_psl.1.0.0.UPF","7d58810084cac21f60fbe77ea2b688fd","100PAW",480.0),
		Kr("SSSP_precision",50.0,4.0,"Kr_ONCV_PBE-1.0.oncvpsp.upf","f2280ecf57a6c8a47e066f0532d843fa","SG15",200.0),
		La("SSSP_precision",40.0,8.0,"La.GGA-PBE-paw-v1.0.UPF","9bc570786a79c122988210fab848eb7f","Wentzcovitch",320.0),
		Li("SSSP_precision",40.0,8.0,"li_pbe_v1.4.uspp.F.UPF","e912e257baa3777c20ea3d68f190483c","GBRV-1.4",320.0),
		Lu("SSSP_precision",45.0,8.0,"Lu.GGA-PBE-paw-v1.0.UPF","cc59902dbb0747cc98260d4f1c8f461e","Wentzcovitch",360.0),
		Mg("SSSP_precision",45.0,8.0,"mg_pbe_v1.4.uspp.F.UPF","8ffbd8f729fef71095aac5bd8316fb1f","GBRV-1.4",360.0),
		Mn("SSSP_precision",90.0,12.0,"mn_pbe_v1.5.uspp.F.UPF","82ef2b46521d7a7d9e736dc3972e4928","GBRV-1.5",1080.0),
		Mo("SSSP_precision",35.0,4.0,"Mo_ONCV_PBE-1.0.oncvpsp.upf","1b5d28e075c9ccadda658a603575cd1f","SG15",140.0),
		N("SSSP_precision",80.0,4.0,"N.oncvpsp.upf","563d65bfb082928f0c9eb97172f6c357","Dojo",320.0),
		Na("SSSP_precision",100.0,4.0,"Na_ONCV_PBE-1.0.oncvpsp.upf","24a298df0a6742ae313db96548fdb2a4","SG15",400.0),
		Nb("SSSP_precision",40.0,8.0,"Nb.pbe-spn-kjpaw_psl.0.3.0.UPF","411d72ad547312f8017e2943ceca08cc","031PAW",320.0),
		Nd("SSSP_precision",40.0,8.0,"Nd.GGA-PBE-paw-v1.0.UPF","6ed08d5e4060cc1ad99b3d24ba8e637d","Wentzcovitch",320.0),
		Ne("SSSP_precision",50.0,4.0,"Ne_ONCV_PBE-1.0.oncvpsp.upf","9b5acc4cb48b9d80e669eadd528e4e8f","SG15",200.0),
		Ni("SSSP_precision",50.0,8.0,"ni_pbe_v1.4.uspp.F.UPF","1ee80287db30b12d2bc1f57a5b5d6409","GBRV-1.4",400.0),
		O("SSSP_precision",75.0,8.0,"O.pbe-n-kjpaw_psl.0.1.UPF","0234752ac141de4415c5fc33072bef88","031PAW",600.0),
		Os("SSSP_precision",40.0,8.0,"Os_pbe_v1.2.uspp.F.UPF","a3fb40a04f0c37c25c34bbc47164c9a8","GBRV-1.2",320.0),
		P("SSSP_precision",30.0,8.0,"P.pbe-n-rrkjus_psl.1.0.0.UPF","8b930f418f0a4573dca56cd030ffe088","100US",240.0),
		Pb("SSSP_precision",45.0,8.0,"Pb.pbe-dn-kjpaw_psl.0.2.2.UPF","9d431e6316058b74ade52399a6cf67da","031PAW",360.0),
		Pd("SSSP_precision",50.0,4.0,"Pd_ONCV_PBE-1.0.oncvpsp.upf","eb77f42b51d86fb18e25f68156a31cf1","SG15",200.0),
		Pm("SSSP_precision",40.0,8.0,"Pm.GGA-PBE-paw-v1.0.UPF","19bca56110d8480befcb833617dbc7df","Wentzcovitch",320.0),
		Po("SSSP_precision",80.0,8.0,"Po.pbe-dn-rrkjus_psl.1.0.0.UPF","3f8a5a8b7a531f42ca8381c21d3cd528","100US",640.0),
		Pr("SSSP_precision",40.0,8.0,"Pr.GGA-PBE-paw-v1.0.UPF","8bd2f9d65236044fbf839895b9bd72c8","Wentzcovitch",320.0),
		Pt("SSSP_precision",100.0,8.0,"Pt.pbe-spfn-rrkjus_psl.1.0.0.UPF","ed006ba81d2b6b3b17616bb61ae12f04","100US",800.0),
		Rb("SSSP_precision",30.0,4.0,"Rb_ONCV_PBE-1.0.oncvpsp.upf","55a5172d6bfbce6759a58e35d43f6aa9","SG15",120.0),
		Re("SSSP_precision",30.0,8.0,"Re_pbe_v1.2.uspp.F.UPF","85f993410f3e006da9d71c142b4ad953","GBRV-1.2",240.0),
		Rh("SSSP_precision",55.0,4.0,"Rh_ONCV_PBE-1.0.oncvpsp.upf","ba07c69523b14cacd10683cd4c4284c1","SG15",220.0),
		Rn("SSSP_precision",200.0,8.0,"Rn.pbe-dn-kjpaw_psl.1.0.0.UPF","03f6b960ab99273412830d0b4aa01365","100PAW",1600.0),
		Ru("SSSP_precision",35.0,4.0,"Ru_ONCV_PBE-1.0.oncvpsp.upf","be037bb81c227cfb9b1461a9f099f4bd","SG15",140.0),
		S("SSSP_precision",35.0,8.0,"s_pbe_v1.4.uspp.F.UPF","88d86576ff6df21479756cfb9bdac1df","GBRV-1.4",280.0),
		Sb("SSSP_precision",55.0,8.0,"sb_pbe_v1.4.uspp.F.UPF","9bc50dfb53373b713f5709b9110fe27f","GBRV-1.4",440.0),
		Sc("SSSP_precision",90.0,8.0,"Sc.pbe-spn-kjpaw_psl.0.2.3.UPF","2c6607fffa759d1e5292e48f5ddd8baa","031PAW",720.0),
		Se("SSSP_precision",30.0,8.0,"Se_pbe_v1.uspp.F.UPF","1b3568f3a8ae88f9a2a0ad0698632c85","GBRV-1.2",240.0),
		Si("SSSP_precision",30.0,8.0,"Si.pbe-n-rrkjus_psl.1.0.0.UPF","0b0bb1205258b0d07b9f9672cf965d36","100US",240.0),
		Sm("SSSP_precision",40.0,8.0,"Sm.GGA-PBE-paw-v1.0.UPF","3ddcafad514a6ea7d14a52e8ca30603a","Wentzcovitch",320.0),
		Sn("SSSP_precision",70.0,8.0,"Sn_pbe_v1.uspp.F.UPF","4cf58ce39ec5d5d420df3dd08604eb00","GBRV-1.2",560.0),
		Sr("SSSP_precision",40.0,8.0,"Sr_pbe_v1.uspp.F.UPF","6b418c05fbe9db5448babca5e47b7a5b","GBRV-1.2",320.0),
		Ta("SSSP_precision",50.0,8.0,"Ta_pbe_v1.uspp.F.UPF","f8bbe9446314a3b8ea5d9f3e3836c939","GBRV-1.2",400.0),
		Tb("SSSP_precision",40.0,8.0,"Tb.GGA-PBE-paw-v1.0.UPF","37cc37188d4ce4bd414f4b03d8f3cab6","Wentzcovitch",320.0),
		Tc("SSSP_precision",40.0,4.0,"Tc_ONCV_PBE-1.0.oncvpsp.upf","1c2b1e6c8b361b656073c0c20ed4f60a","SG15",160.0),
		Te("SSSP_precision",30.0,8.0,"Te_pbe_v1.uspp.F.UPF","c319670d6894cc26e93307826a071b75","GBRV-1.2",240.0),
		Ti("SSSP_precision",40.0,8.0,"ti_pbe_v1.4.uspp.F.UPF","88a00a6731bd790ddea75d31a80cb452","GBRV-1.4",320.0),
		Tl("SSSP_precision",70.0,8.0,"Tl_pbe_v1.2.uspp.F.UPF","b76cf1f7e72655a2b2c53cf6385d7059","GBRV-1.2",560.0),
		Tm("SSSP_precision",40.0,8.0,"Tm.GGA-PBE-paw-v1.0.UPF","5bf2bc9b2000dc366ce20ce5239c3999","Wentzcovitch",320.0),
		V("SSSP_precision",40.0,8.0,"v_pbe_v1.4.uspp.F.UPF","22b79981416ebb76fdaf5b1b8640f6fb","GBRV-1.4",320.0),
		W("SSSP_precision",50.0,8.0,"W_pbe_v1.2.uspp.F.UPF","9c083fa34c2a2ea0f02f1f893e16e1c8","GBRV-1.2",400.0),
		Xe("SSSP_precision",80.0,4.0,"Xe_ONCV_PBE-1.1.oncvpsp.upf","f6ea899d5a535d3f5731d9e48edfe3e3","SG15-1.1",320.0),
		Y("SSSP_precision",35.0,8.0,"Y_pbe_v1.uspp.F.UPF","2cf71db95cafeb975fc457bd7f14888e","GBRV-1.2",280.0),
		Yb("SSSP_precision",40.0,8.0,"Yb.GGA-PBE-paw-v1.0.UPF","c46ad346ad0f6b1727467da500789f7b","Wentzcovitch",320.0),
		Zn("SSSP_precision",90.0,8.0,"Zn_pbe_v1.uspp.F.UPF","df62231357ef9e81f77b2b3087fa5675","GBRV-1.2",720.0),
		Zr("SSSP_precision",30.0,8.0,"Zr_pbe_v1.uspp.F.UPF","5db81b1e868ab7776c4564c113de050b","GBRV-1.2",240.0)
		;

	    private final String folderName;
		private final double ecutwfc;//Ry
		private final double dual;
		private final String fileName;
		private final String md5Str;
		private final String ppType;
		private final double ecutrho;//Ry

	    private Precision(String folderName, double ecutwfc, double dual, String fileName, String md5Str, String ppType, double ecutrho) {
	    	this.folderName = folderName;
	    	this.ecutwfc = ecutwfc;
	    	this.dual = dual;
	    	this.fileName = fileName;
	    	this.md5Str = md5Str;
	    	this.ppType = ppType;
	    	this.ecutrho = ecutrho;
	    }

		public double getEcutwfc() {return ecutwfc;}
		public double getDual() {return dual;}
		public String getFileName() {return fileName;}//necessary
		public String getMd5Str() {return md5Str;}
		public String getPpType() {return ppType;}
		public double getEcutrho() {return ecutrho;}
		public String getFolderName() {return folderName;}//necessary
	}
}
